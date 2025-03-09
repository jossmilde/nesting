const express = require('express');
const multer = require('multer');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
const upload = multer({ dest: 'uploads/' });

// Log all requests for debugging
app.use((req, res, next) => {
    console.log(`Request: ${req.method} ${req.url}`);
    next();
});

// Serve static files from 'public'
app.use(express.static(path.join(__dirname, 'public')));
console.log('Serving static files from:', path.join(__dirname, 'public'));

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.post('/api/preview3d', upload.single('file'), (req, res) => {
    const filePath = req.file.path;
    console.log(`Processing file: ${req.file.originalname}`);
    exec(`python preview3d.py "${filePath}"`, (error, stdout, stderr) => {
        if (error) {
            console.error(`Python error: ${error}`);
            res.status(500).json({ error: error.message });
            return;
        }
        console.error(stderr);
        console.log('Preview stdout:', stdout);
        res.json(JSON.parse(stdout));
        fs.unlink(filePath, (err) => {
            if (err) console.error(`Failed to delete file: ${err}`);
        });
    });
});

app.post('/api/nest', upload.single('file'), (req, res) => {
    const filePath = req.file.path;
    const { sheetWidth, sheetHeight, spacing } = req.body;
    console.log(`Nesting file: ${req.file.originalname} with width=${sheetWidth}, height=${sheetHeight}, spacing=${spacing}`);
    exec(`python nest.py "${filePath}" ${sheetWidth} ${sheetHeight} ${spacing}`, (error, stdout, stderr) => {
        if (error) {
            console.error(`Nest error: ${error}`);
            res.status(500).json({ error: error.message });
            return;
        }
        console.error(stderr);
        console.log('Nest stdout:', stdout);
        res.json(JSON.parse(stdout));
        fs.unlink(filePath, (err) => {
            if (err) console.error(`Failed to delete file: ${err}`);
        });
    });
});

app.listen(3000, () => {
    console.log('Server running on port 3000');
});