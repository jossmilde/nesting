const express = require('express');
const multer = require('multer');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
const upload = multer({ dest: 'uploads/' });

app.use((req, res, next) => {
    console.log(`Request: ${req.method} ${req.url}`);
    next();
});

app.use(express.static(path.join(__dirname, 'public')));
console.log('Serving static files from:', path.join(__dirname, 'public'));

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.post('/api/preview3d', upload.array('files'), (req, res) => {
    const filePaths = req.files.map(file => file.path);
    console.log(`Processing files: ${req.files.map(f => f.originalname).join(', ')}`);
    exec(`python preview3d.py "${filePaths[0]}"`, (error, stdout, stderr) => {
        if (error) {
            console.error(`Python error: ${error}`);
            res.status(500).json({ error: error.message });
            return;
        }
        console.error(stderr);
        console.log('Preview stdout:', stdout);
        res.json(JSON.parse(stdout));
        filePaths.forEach(filePath => {
            fs.unlink(filePath, (err) => {
                if (err) console.error(`Failed to delete file: ${err}`);
            });
        });
    });
});

app.post('/api/nest', upload.array('files'), (req, res) => {
    const filePaths = req.files.map(file => file.path);
    const quantities = JSON.parse(req.body.quantities);
    const colors = JSON.parse(req.body.colors);
    const { sheetWidth, sheetHeight, spacing, sheetGap, faceDown } = req.body;
    console.log(`Nesting files: ${req.files.map(f => f.originalname).join(', ')} with quantities=${quantities}, colors=${JSON.stringify(colors)}, width=${sheetWidth}, height=${sheetHeight}, spacing=${spacing}, sheetGap=${sheetGap}, faceDown=${faceDown}`);
    const fileArgs = filePaths.map((path, i) => `"${path}" ${quantities[i]}`).join(' ');
    exec(`python nest.py ${fileArgs} ${sheetWidth} ${sheetHeight} ${spacing} ${sheetGap} ${faceDown}`, (error, stdout, stderr) => {
        if (error) {
            console.error(`Nest error: ${error}`);
            res.status(500).json({ error: error.message });
            return;
        }
        console.error(stderr);
        console.log('Nest stdout:', stdout);
        const result = JSON.parse(stdout);
        result.parts.forEach((part, i) => {
            if (i < colors.length) part.color = colors[i];
        });
        res.json(result);
        // No cleanup here to keep files for STEP generation
    });
});

app.post('/api/download_nest', express.json(), (req, res) => {
    const nestData = req.body;
    const tempFile = path.join(__dirname, 'uploads', 'temp_nest.json');
    const stepFile = path.join(__dirname, 'public', 'nested_parts.step');
    console.log('Generating STEP file with data:', JSON.stringify(nestData));
    
    try {
        fs.writeFileSync(tempFile, JSON.stringify(nestData));
        console.log(`Wrote temp JSON to ${tempFile}`);
    } catch (err) {
        console.error(`Failed to write temp JSON: ${err}`);
        res.status(500).json({ error: 'Failed to write temp file' });
        return;
    }

    exec(`python generate_step.py "${tempFile}" "${stepFile}"`, (error, stdout, stderr) => {
        if (error) {
            console.error(`STEP generation error: ${error.message}`);
            console.error(`STDERR: ${stderr}`);
            res.status(500).json({ error: `STEP generation failed: ${error.message}` });
            return;
        }
        console.error(stderr);
        console.log('STEP stdout:', stdout);
        if (fs.existsSync(stepFile)) {
            console.log(`STEP file generated at ${stepFile}`);
            res.sendFile(stepFile, (err) => {
                if (err) {
                    console.error(`Send file error: ${err}`);
                    res.status(500).send('Error sending file');
                }
                fs.unlink(tempFile, (err) => { if (err) console.error(`Cleanup error: ${err}`); });
                fs.unlink(stepFile, (err) => { if (err) console.error(`Cleanup error: ${err}`); });
                if (nestData.original_files) {
                    nestData.original_files.forEach(filePath => {
                        fs.unlink(filePath, (err) => { if (err) console.error(`Cleanup error: ${err}`); });
                    });
                }
            });
        } else {
            console.error('STEP file not found:', stepFile);
            res.status(500).send('STEP file not generated');
        }
    });
});

app.listen(3000, () => {
    console.log('Server running on port 3000');
});