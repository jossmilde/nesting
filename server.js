const express = require('express');
const multer = require('multer');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const app = express();

const upload = multer({ dest: 'uploads/' });
app.use(express.static('public'));

app.post('/api/preview3d', upload.single('file'), (req, res) => {
    console.log(`Processing file: ${req.file.originalname}`);
    // Use the full path to the nesting env's Python
    const pythonPath = 'C:\\ProgramData\\anaconda3\\envs\\nesting\\python.exe'; // Adjust this!
    const python = spawn(pythonPath, ['preview3d.py', req.file.path]);
    let output = '';
    python.stdout.on('data', (data) => {
        output += data;
        console.log(`Python stdout: ${data}`);
    });
    python.stderr.on('data', (data) => console.error(`Python error: ${data.toString()}`));
    python.on('error', (err) => {
        console.error(`Failed to spawn Python: ${err.message}`);
        res.status(500).send('Python execution failed');
    });
    python.on('close', (code) => {
        fs.unlinkSync(req.file.path);
        if (code !== 0) {
            console.error(`Python exited with code ${code}`);
            res.status(500).send('Preview generation failed');
        } else if (!output.trim()) {
            console.error('No output from Python script');
            res.status(500).send('No preview data received');
        } else {
            try {
                res.json(JSON.parse(output));
            } catch (err) {
                console.error(`JSON parse error: ${err.message}, output: "${output}"`);
                res.status(500).send('Invalid preview data');
            }
        }
    });
});

app.listen(3000, () => console.log('Server running on port 3000'));