// Bestand: server.js (v0.11 - Directe stdout/stderr, geen logbestand)

const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const { exec } = require('child_process');

const app = express();
const port = process.env.PORT || 3000;

// --- Basis Configuratie ---
const uploadDir = path.join(__dirname, 'uploads');
const publicDir = path.join(__dirname, 'public');
const tempDir = path.join(__dirname, 'temp_jobs');
const pythonStepScriptPath = path.join(__dirname, 'process_step.py');
const pythonNestingScriptPath = path.join(__dirname, 'run_nesting.py');

// Pad naar Python executable (PAS DIT AAN INDIEN NODIG)
const PYTHON_EXECUTABLE = "python";

// Zorg dat mappen bestaan
[uploadDir, publicDir, tempDir].forEach(dir => {
    if (!fs.existsSync(dir)) {
        try { fs.mkdirSync(dir, { recursive: true }); console.log(`Directory created: ${dir}`); }
        catch (err) { console.error(`Error creating directory ${dir}: ${err}`); process.exit(1); }
    }
});

// --- Middleware ---
app.use(express.static(publicDir));
app.use(express.json({ limit: '10mb' }));

// --- Multer Configuratie ---
const storage = multer.diskStorage({ destination: (req, file, cb) => cb(null, uploadDir), filename: (req, file, cb) => { const u = Date.now() + '-' + Math.round(Math.random() * 1E9); const e = path.extname(file.originalname); cb(null, 'upload-' + u + e); } });
const fileFilter = (req, file, cb) => { const a = ['.step', '.stp']; const e = path.extname(file.originalname).toLowerCase(); if (a.includes(e)) { cb(null, true); } else { cb(new Error('INVALID_TYPE')); } };
const upload = multer({ storage: storage, fileFilter: fileFilter, limits: { fileSize: 100 * 1024 * 1024, files: 50 } }).array('files[]', 50);

// --- Helper Functie: Roep process_step.py aan ---
async function processStepFile(filePath, originalName) {
    console.log(`[${new Date().toISOString()}] [PROCESS STEP] Calling Python for ${originalName}`);
    const command = `"${PYTHON_EXECUTABLE}" "${pythonStepScriptPath}" "${filePath}"`;

    return new Promise((resolve) => {
        exec(command, { maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
            let resultData = null;
            let parseError = null;

            if (error) {
                console.error(`[Exec Error] process_step.py ${originalName}: ${error.message}`);
                console.error(`Stderr: ${stderr}`);
                try { const errResult = JSON.parse(stderr); resolve({ success: false, error: errResult.error || "Python stderr error", details: errResult.details, traceback: errResult.traceback }); }
                catch (ignoreErr) { resolve({ success: false, error: `Python script exec error: ${stderr || error.message}` }); }
                return;
            }
            if (stderr && !stderr.includes("DeprecationWarning") && !stderr.match(/^\s*$/)) { console.warn(`[Exec Stderr] process_step.py ${originalName}: ${stderr}`); }

            try {
                if (stdout && stdout.trim().length > 0) {
                    resultData = JSON.parse(stdout);
                    if (resultData.success === false) { console.error(`[Python Logic Error] ${originalName}: ${resultData.error}`); }
                    resolve(resultData);
                } else { console.error(`[Exec Error] process_step.py ${originalName}: Empty stdout received.`); resolve({ success: false, error: "Python script gaf geen output." + (stderr ? " Stderr: " + stderr.trim() : "") }); }
            } catch (err) { parseError = err; console.error(`[JSON Parse Fout] ${originalName}: ${parseError.message}. Stdout was: ${stdout}`); resolve({ success: false, error: `Kon Python output niet parsen.${stderr ? ' Stderr: ' + stderr.trim() : ''}` }); }
        });
    });
}

// --- Helper Functie: Roep run_nesting.py aan ---
async function processNestingJob(jobData) {
    const jobId = `job-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
    const tempFilePath = path.join(tempDir, `${jobId}.json`);
    console.log(`[${new Date().toISOString()}] [PROCESS NESTING] Starting job ${jobId}`);

    try {
        const jsonString = JSON.stringify(jobData, null, 2);
        await fs.promises.writeFile(tempFilePath, jsonString, 'utf8');
        console.log(`[${new Date().toISOString()}] [PROCESS NESTING] Job data written to ${tempFilePath}`);

        const command = `"${PYTHON_EXECUTABLE}" "${pythonNestingScriptPath}" "${tempFilePath}"`;
        console.log(`[${new Date().toISOString()}] [PROCESS NESTING] Executing: ${command}`);

        const resultPromise = new Promise((resolve) => {
            exec(command, { maxBuffer: 50 * 1024 * 1024 }, (error, stdout, stderr) => { // Verhoogde buffer
                let resultData = null;
                let parseError = null;

                // Log stderr direct naar de console (dit zal nu veel minder zijn)
                if (stderr && !stderr.match(/^\s*$/)) {
                     console.warn(`[Exec Stderr] run_nesting.py ${jobId}: ${stderr.trim()}`);
                 }

                if (error && error.code !== 0) {
                    console.error(`[Exec Error] run_nesting.py ${jobId} (Code: ${error.code}): ${error.message}`);
                    // Probeer eventuele resterende JSON error uit stderr te halen
                    try {
                         const errResult = JSON.parse(stderr.substring(stderr.lastIndexOf('{')));
                         resolve({ success: false, message: "Fout tijdens nesting (Python stderr).", error: errResult.error || stderr, details: errResult.details });
                     } catch (ignoreErr) {
                         resolve({ success: false, message: "Fout tijdens nesting (Python exec).", error: stderr || error.message });
                     }
                    return;
                }

                // Probeer stdout te parsen
                try {
                    if (stdout && stdout.trim().length > 0) {
                         resultData = JSON.parse(stdout);
                         if (resultData.success === false) { console.error(`[Python Nesting Logic Error] ${jobId}: ${resultData.message}`); }
                         resolve(resultData);
                     } else {
                         console.error(`[Exec Error] run_nesting.py ${jobId}: Empty stdout received.`);
                         resolve({ success: false, message: "Nesting script gaf geen JSON output." + (stderr ? " Stderr: " + stderr.trim() : "") });
                     }
                } catch (err) {
                    parseError = err;
                    console.error(`[JSON Parse Fout] run_nesting.py ${jobId}: ${parseError.message}. Stdout: ${stdout}`);
                     resolve({ success: false, message: "Kon resultaat van nesting script niet parsen.", error: parseError.message });
                }
            });
        });

        const result = await resultPromise;
        return result;

    } catch (err) {
        console.error(`[${new Date().toISOString()}] [PROCESS NESTING] Error processing job ${jobId}:`, err);
        return { success: false, message: "Serverfout bij voorbereiden nesting job.", error: err.message };
    } finally {
        try { if (fs.existsSync(tempFilePath)) { await fs.promises.unlink(tempFilePath); console.log(`[${new Date().toISOString()}] [PROCESS NESTING] Temporary job file ${tempFilePath} deleted.`); } }
        catch (cleanupErr) { console.error(`[${new Date().toISOString()}] [PROCESS NESTING] Error deleting temporary file ${tempFilePath}:`, cleanupErr); }
    }
}

// --- Express Routes ---
app.post('/upload', async (req, res) => {
    upload(req, res, async (err) => {
        if (err instanceof multer.MulterError && err.code === 'LIMIT_FILE_COUNT') { return res.status(400).json({ success: false, message: `Upload mislukt: Maximaal 50 bestanden tegelijk toegestaan.` }); }
        else if (err instanceof multer.MulterError) { return res.status(400).json({ success: false, message: `Upload fout (${err.code})` }); }
        else if (err?.message === 'INVALID_TYPE') { return res.status(400).json({ success: false, message: 'Ongeldig bestandstype.' }); }
        else if (err) { return res.status(500).json({ success: false, message: 'Serverfout tijdens upload middleware.' }); }
        if (!req.files?.length) { return res.status(400).json({ success: false, message: 'Geen bestanden geselecteerd.' }); }

        console.log(`[${new Date().toISOString()}] ${req.files.length} file(s) received. Processing...`);
        const results = [];
        for (const file of req.files) {
            const fileInfo = { originalName: file.originalname, filename: file.filename, path: file.path, size: file.size };
            let processResult = undefined;
            try {
                processResult = await processStepFile(fileInfo.path, fileInfo.originalName);
                if (typeof processResult === 'undefined') { console.error(`[${new Date().toISOString()}] CRITICAL: processStepFile resolved undefined for ${fileInfo.originalName}`); results.push({ ...fileInfo, processingResult: { success: false, error: "Interne serverfout: Kon onderdeel niet verwerken." } }); continue; }
                results.push({ ...fileInfo, processingResult: processResult });
                console.log(`[${new Date().toISOString()}] Processed ${fileInfo.originalName}: Success=${processResult.success}`);
            } catch (processError) { console.error(`[${new Date().toISOString()}] Unhandled Error processing ${fileInfo.originalName}: ${processError.message}`); results.push({ ...fileInfo, processingResult: { success: false, error: processError.message || "Onbekende verwerkingsfout." } }); }
        }
        console.log(`[${new Date().toISOString()}] Upload processing finished. Sending response.`);
        res.status(200).json({ success: true, message: `Verwerking van ${results.length} bestand(en) voltooid.`, results: results });
        results.forEach(r => { if (r.path && fs.existsSync(r.path)) { fs.unlink(r.path, e => { if(e) console.error(`Cleanup err ${r.path}:`, e?.message); }); }});
    });
});

app.post('/nest', async (req, res) => {
    console.log(`[${new Date().toISOString()}] Ontvangst POST request op /nest`);
    const nestingJobData = req.body;
    console.log("Ontvangen Nesting Job Data (parts count: %d, sheets count: %d)", nestingJobData?.parts?.length ?? 0, nestingJobData?.sheets?.length ?? 0);

    if (!nestingJobData || typeof nestingJobData !== 'object' || !nestingJobData.parts || !nestingJobData.sheets) { console.error("Ontvangen ongeldige data op /nest"); return res.status(400).json({ success: false, message: "Ongeldige nesting data ontvangen." }); }
    if (nestingJobData.parts.length === 0 || nestingJobData.sheets.length === 0) { return res.status(400).json({ success: false, message: "Geen onderdelen of platen opgegeven." }); }

    try {
        const nestingResult = await processNestingJob(nestingJobData);
        if (nestingResult.success) { res.status(200).json(nestingResult); }
        else { console.error("Nesting process returned failure:", nestingResult); res.status(200).json(nestingResult); }
    } catch (error) { console.error(`[${new Date().toISOString()}] Fout in /nest endpoint:`, error); res.status(500).json({ success: false, message: "Interne serverfout tijdens starten nesting.", error: error.message }); }
});

// --- Globale Error Handler & Server Start ---
app.use((err, req, res, next) => { console.error("Unhandled Express error:", err.stack); res.status(500).json({ success: false, message: 'Interne serverfout.' }); });
app.listen(port, () => { console.log(`Server gestart op http://localhost:${port}`); });
process.on('SIGINT', () => { console.log("\nServer afsluiten..."); process.exit(0); });