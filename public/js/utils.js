// Bestand: public/js/utils.js
// Bevat nu alleen algemene, niet-DOM-specifieke helpers

// --- START FUNCTION showStatus ---
export function showStatus(statusMessagesDiv, message, type = 'info') {
    // Check of het element bestaat
    if (!statusMessagesDiv || !(statusMessagesDiv instanceof Element)) {
        console.error("showStatus: Ongeldig of ontbrekend statusMessagesDiv element meegegeven.");
        return;
    }
    statusMessagesDiv.innerHTML = message;
    statusMessagesDiv.className = `status-${type}`;
    statusMessagesDiv.style.display = 'block';
}
// --- END FUNCTION showStatus ---

// --- START FUNCTION clearStatus ---
export function clearStatus(statusMessagesDiv) {
     if (!statusMessagesDiv || !(statusMessagesDiv instanceof Element)) {
         // console.warn("clearStatus: statusMessagesDiv niet gevonden of ongeldig."); // Minder strict
         return;
     }
    statusMessagesDiv.textContent = '';
    statusMessagesDiv.style.display = 'none';
    statusMessagesDiv.className = '';
}
// --- END FUNCTION clearStatus ---

// --- START FUNCTION calculateProfileBoundingBox ---
export function calculateProfileBoundingBox(outerLoop) {
    // Check of input een array is
    if (!outerLoop || !Array.isArray(outerLoop) || outerLoop.length === 0) {
        // console.warn("calculateProfileBoundingBox: Ongeldige of lege outerLoop input.");
        return { width: 0, height: 0, minX: 0, minY: 0, maxX: 0, maxY: 0 };
    }
    // Initialiseer met Infinity om zeker te zijn dat eerste punt correct wordt
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    let validPointFound = false;
    // Loop door punten
    for (const p of outerLoop) {
        // Check of punt een array van 2 getallen is
        if (Array.isArray(p) && p.length === 2 && typeof p[0] === 'number' && typeof p[1] === 'number' && !isNaN(p[0]) && !isNaN(p[1])) {
            minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]);
            minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]);
            validPointFound = true; // Markeer dat we tenminste één geldig punt hadden
        } else {
             console.warn("Invalid point skipped in calculateProfileBoundingBox:", p);
        }
    }
    // Als geen enkel punt geldig was, retourneer nullen
    if (!validPointFound) {
         console.warn("calculateProfileBoundingBox: Geen valide punten gevonden in outerLoop.");
         return { width: 0, height: 0, minX: 0, minY: 0, maxX: 0, maxY: 0 };
    }
    // Bereken en rond af
    let width = Math.round((maxX - minX)*100)/100;
    let height = Math.round((maxY - minY)*100)/100;
    return { width: width, height: height, minX: minX, minY: minY, maxX: maxX, maxY: maxY };
}
// --- END FUNCTION calculateProfileBoundingBox ---

// --- START FUNCTION pointsToSvgPath ---
export function pointsToSvgPath(points) {
    if (!points || !Array.isArray(points) || points.length < 2) { return ""; }
    // Filter ongeldige punten vooraf
    const validPoints = points.filter(p => Array.isArray(p) && p.length === 2 && !isNaN(p[0]) && !isNaN(p[1]));
    if (validPoints.length < 2) { return ""; } // Nog steeds minder dan 2 valide punten?

    // Bouw pad string op
    let pathString = `M ${validPoints[0][0]} ${validPoints[0][1]}`;
    for (let i = 1; i < validPoints.length; i++) {
        pathString += ` L ${validPoints[i][0]} ${validPoints[i][1]}`;
    }
    pathString += " Z"; // Sluit pad
    return pathString;
}
// --- END FUNCTION pointsToSvgPath ---

// --- START FUNCTION transformPoints ---
export function transformPoints(points, dx, dy, angleDeg, rotateOriginX = 0, rotateOriginY = 0) {
    if (!points) { return []; }
    const angleRad = angleDeg * Math.PI / 180.0;
    const cosA = Math.cos(angleRad);
    const sinA = Math.sin(angleRad);
    return points.map(p => {
        if (!Array.isArray(p) || p.length !== 2 || isNaN(p[0]) || isNaN(p[1])) { return null; } // Markeer ongeldig
        const tX = p[0] - rotateOriginX;
        const tY = p[1] - rotateOriginY;
        const rX = tX * cosA - tY * sinA;
        const rY = tX * sinA + tY * cosA;
        const fX = rX + rotateOriginX + dx;
        const fY = rY + rotateOriginY + dy;
        return [fX, fY];
    }).filter(p => p !== null); // Verwijder ongeldige punten uit resultaat
}
// --- END FUNCTION transformPoints ---

// --- START FUNCTION defaultdict (Helper) ---
export function defaultdict(defaultFactory) {
    return new Proxy({}, {
        get: (target, name) => {
            // Property access interceptor
            if (name in target) {
                // Property exists, return it
                return target[name];
            } else {
                // Property doesn't exist, create it using the factory
                const newValue = defaultFactory();
                target[name] = newValue;
                return newValue;
            }
        }
    });
}
// --- END FUNCTION defaultdict ---

// --- START FUNCTION findSheetInfoById (Helper) ---
export function findSheetInfoById(sheetInstanceId, allSheetDefinitions) {
    if (!sheetInstanceId || !allSheetDefinitions) { return null; }
    // Probeer originele ID te parsen
    const match = sheetInstanceId.match(/^(manual_\d+|part_upload-\d+-\d+\.step)_inst_\d+$/);
    let originalSheetId = null;
    if (match && match[1]) {
        originalSheetId = match[1];
    } else {
        // Fallback: verwijder '_inst_...' indien aanwezig
        originalSheetId = sheetInstanceId.replace(/_inst_\d+$/, '');
    }
    // Zoek in de lijst
    const foundSheet = allSheetDefinitions.find(sheet => sheet.id === originalSheetId);
    if (!foundSheet) {
        console.warn(`Sheet definition not found for original ID: ${originalSheetId} (derived from instance ${sheetInstanceId})`);
    }
    return foundSheet;
}
// --- END FUNCTION findSheetInfoById ---