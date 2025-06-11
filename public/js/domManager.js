// Bestand: public/js/domManager.js
// Bevat functies die de DOM direct manipuleren (tabel, resultaten, etc.)

// Importeer benodigde functies uit andere modules
import { cleanupThreeInstance, render3DPreview } from './threeManager.js';
// --- Utils Import (clearStatus toegevoegd, drawSheetLayout HIERONDER gedefinieerd!) ---
import { calculateProfileBoundingBox, pointsToSvgPath, transformPoints, defaultdict, findSheetInfoById, clearStatus } from './utils.js';
// import { drawSheetLayout } from './svgUtils.js'; // <<< DEZE REGEL VERWIJDERD/GECORRIGEERD

// --- START FUNCTION addManualSheetDefinition ---
export function addManualSheetDefinition(manualSheetsContainer, noManualSheetsMsg, manualSheetCounter) {
    if (!manualSheetsContainer || !noManualSheetsMsg) { console.error("Cannot find manual sheet container"); return manualSheetCounter; }
    noManualSheetsMsg.style.display = 'none';
    manualSheetCounter++;
    const entryDiv = document.createElement('div'); entryDiv.className = 'manual-sheet-entry'; entryDiv.id = `manual-sheet-${manualSheetCounter}`;
    const fragment = document.createDocumentFragment(); const fields = [ { id: 'width', label: 'B(mm)', value: 2500, min: 1, step: 'any' }, { id: 'height', label: 'H(mm)', value: 1250, min: 1, step: 'any' }, { id: 'thickness', label: 'D(mm)', value: 3, min: 0, step: 'any' }, { id: 'quantity', label: 'Aantal', value: 1, min: 1, step: 1 } ];
    fields.forEach(field => { const div = document.createElement('div'); const labelEl = document.createElement('label'); const inputEl = document.createElement('input'); const inputId = `manual-${field.id}-${manualSheetCounter}`; labelEl.htmlFor = inputId; labelEl.textContent = field.label; inputEl.type = 'number'; inputEl.id = inputId; inputEl.name = `manual-${field.id}[]`; inputEl.min = field.min; inputEl.step = field.step; inputEl.value = field.value; inputEl.required = true; div.appendChild(labelEl); div.appendChild(inputEl); fragment.appendChild(div); });
    const removeContainer = document.createElement('div'); removeContainer.className = 'remove-btn-container'; const removeBtn = document.createElement('button'); removeBtn.type = 'button'; removeBtn.className = 'remove-sheet-btn'; removeBtn.dataset.target = entryDiv.id; removeBtn.title = 'Verwijder'; removeBtn.textContent = 'X';
    removeBtn.addEventListener('click', () => removeManualSheetDefinition(removeBtn, manualSheetsContainer, noManualSheetsMsg));
    removeContainer.appendChild(removeBtn); fragment.appendChild(removeContainer); entryDiv.appendChild(fragment); manualSheetsContainer.appendChild(entryDiv);
    return manualSheetCounter;
}
// --- END FUNCTION addManualSheetDefinition ---

// --- START FUNCTION removeManualSheetDefinition ---
export function removeManualSheetDefinition(buttonElement, manualSheetsContainer, noManualSheetsMsg) {
    const targetId = buttonElement.dataset.target; const entryToRemove = document.getElementById(targetId);
    if (entryToRemove && entryToRemove.parentNode === manualSheetsContainer) { entryToRemove.remove(); if (manualSheetsContainer && !manualSheetsContainer.querySelector('.manual-sheet-entry') && noManualSheetsMsg) { noManualSheetsMsg.style.display = 'block'; } }
    else { console.warn(`Cannot find ${targetId} to remove.`); }
}
// --- END FUNCTION removeManualSheetDefinition ---

// --- START FUNCTION addFileToTable ---
export function addFileToTable(fileResult, uploadedPartsData, threeInstances, uploadedFilesTBody, uploadedFilesTable, noFilesMessage) {
     if (!uploadedFilesTBody || !uploadedFilesTable || !noFilesMessage) { console.error("Tabel niet gevonden!"); return; }
     noFilesMessage.style.display = 'none'; uploadedFilesTable.style.display = '';
     const srv=fileResult.filename;const orig=fileResult.originalName;const type=(orig.split('.').pop()||'').toUpperCase();const pId=`preview-${srv}`;const qId=`quantity-${srv}`;const faceId=`face-select-${srv}`;const sheetCbId=`use-sheet-${srv}`;const sheetQtyId=`sheet-quantity-${srv}`;const sheetVal=srv;const res=fileResult.processingResult;
     const oldRow=document.getElementById(`row-${srv}`);if(oldRow){cleanupThreeInstance(threeInstances, pId);oldRow.remove();}
     const row=uploadedFilesTBody.insertRow();row.id=`row-${srv}`;
     // Cellen
     row.insertCell().textContent=orig; row.insertCell().textContent=type; const thkCell=row.insertCell();if(res.success&&typeof res.thickness==='number'){thkCell.textContent=res.thickness.toFixed(2);thkCell.style.textAlign='right'}else{thkCell.textContent='-';thkCell.style.textAlign='center'}
     const prvCell=row.insertCell();let prvText='<i>Preview niet geladen</i>'; let selHTML='';if(type==='STEP'){selHTML=`<div class="face-selector"><select name="${faceId}" id="${faceId}" disabled title="Kies oriëntatie"><option value="">Laden...</option></select></div>`;} prvCell.innerHTML=`<div class="preview-container"><div class="viewer-placeholder" id="${pId}">${prvText}</div><button type="button" class="load-preview-btn" data-target-id="${pId}" data-filename="${srv}" style="font-size:0.8em;padding:3px 6px;margin-top:5px;">Laad 3D Preview</button>${selHTML}</div>`;
     row.insertCell().innerHTML=`<input type="number" id="${qId}" name="${qId}" value="1" min="1" title="Aantal te nesten">`;const sheetCell=row.insertCell();sheetCell.style.verticalAlign='top';sheetCell.innerHTML=`<input type="checkbox" id="${sheetCbId}" class="use-as-sheet-checkbox" data-quantity-input-id="${sheetQtyId}" title="Vink aan om als plaat te gebruiken"><input type="number" id="${sheetQtyId}" class="sheet-quantity-input" value="1" min="1" title="Aantal beschikbaar als plaat" style="display:none;">`; const actionCell=row.insertCell();actionCell.style.verticalAlign='middle';const rmBtn=document.createElement('button');rmBtn.type='button';rmBtn.className='remove-part-btn';rmBtn.dataset.filename=srv;rmBtn.title='Verwijder';rmBtn.textContent='X';actionCell.appendChild(rmBtn);
     // Dropdown
     const sel=document.getElementById(faceId); if(sel){if(type==='STEP'&&res.success){const pData=uploadedPartsData[srv];if(pData?.facesInfo?.length>0){sel.innerHTML='';const faces=pData.facesInfo;faces.forEach(f=>{const o=document.createElement('option');o.value=f.id;const n=(f.normal||[0,0,0]).map(x=>x.toFixed(2)).join(',');let pfx="";if(f.id===pData.defaultFaceId){pfx="[ROOD Default] ";o.selected=true;}else if(f.id===pData.secondLargestFaceId){pfx="[GROEN 2nd] ";} o.textContent=`${pfx}${f.id} (A:${(f.area||0).toFixed(0)} N:${n})`;sel.appendChild(o)});sel.disabled=false}else{sel.innerHTML='<option value="">Geen vlakken</option>'}}else{sel.innerHTML='<option value="">N.v.t./Fout</option>'}}
     // Geen render aanroep hier
}
// --- END FUNCTION addFileToTable ---

// --- START FUNCTION drawSheetLayout ---
// DEZE FUNCTIE IS HIER GEDEFINIEERD en gebruikt utils
/*export function drawSheetLayout(targetDiv, sheetInfo, placementsOnSheet, visualOutputPlaceholder) {
    if (!targetDiv || !sheetInfo || typeof sheetInfo.width !== 'number' || typeof sheetInfo.height !== 'number') { console.error("Invalid input drawSheetLayout"); targetDiv.innerHTML = '<p style="color:red;">Teken fout.</p>'; if (visualOutputPlaceholder) visualOutputPlaceholder.style.display = 'none'; return; }
    const svgNS = "http://www.w3.org/2000/svg"; targetDiv.innerHTML = ''; if (visualOutputPlaceholder) visualOutputPlaceholder.style.display = 'none';
    const sheetWidth = sheetInfo.width; const sheetHeight = sheetInfo.height;
    const svg = document.createElementNS(svgNS, "svg"); svg.setAttribute("viewBox", `0 0 ${sheetWidth} ${sheetHeight}`); svg.setAttribute("preserveAspectRatio", "xMidYMid meet"); svg.setAttribute("width", "100%"); svg.setAttribute("height", "100%"); svg.style.maxWidth = `${sheetWidth}px`; svg.style.maxHeight = '500px'; svg.style.display = 'block'; svg.style.margin = 'auto';
    const styleDef = document.createElementNS(svgNS, "style"); styleDef.textContent = `.svg-sheet{fill:#fdfdfe;stroke:#a0a0a0;stroke-width:1px;} .svg-part-profile{fill:#cfe2ff;stroke:#052c65;stroke-width:0.7px;opacity:0.85;} .svg-part-label{font-size:10px;font-family:sans-serif;fill:#333;text-anchor:middle;dominant-baseline:central;pointer-events:none;}`; svg.appendChild(styleDef);
    const groupFlipY = document.createElementNS(svgNS, "g"); groupFlipY.setAttribute("transform", `translate(0, ${sheetHeight}) scale(1, -1)`); svg.appendChild(groupFlipY);
    const sheetRect = document.createElementNS(svgNS, "rect"); sheetRect.setAttribute("x", "0"); sheetRect.setAttribute("y", "0"); sheetRect.setAttribute("width", sheetWidth.toString()); sheetRect.setAttribute("height", sheetHeight.toString()); sheetRect.setAttribute("class", "svg-sheet"); groupFlipY.appendChild(sheetRect);

    if (placementsOnSheet?.length > 0) {
        placementsOnSheet.forEach((p) => {
            const prof = p.profile2d; const bboxWithSpacing = p.bbox; if (!prof || !prof.outer || !bboxWithSpacing || typeof bboxWithSpacing.x === 'undefined') { console.warn("Skip placement: no profile/bbox", p); return; }
            const origPoints = prof.outer; const px_bl = bboxWithSpacing.x; const py_bl = bboxWithSpacing.y; const rot = p.rotation || 0;
            const origBbox = calculateProfileBoundingBox(origPoints); // Util
            if (origBbox.width === 0 && origBbox.height === 0 && origPoints.length > 0) return;
            const rotCx = origBbox.minX + origBbox.width / 2; const rotCy = origBbox.minY + origBbox.height / 2;
            const rotatedPoints = transformPoints(origPoints, 0, 0, rot, rotCx, rotCy); // Util
            const rotatedBbox = calculateProfileBoundingBox(rotatedPoints); // Util
            if (rotatedBbox.width === 0 && rotatedBbox.height === 0 && rotatedPoints.length > 0) return;
            const dx = px_bl - rotatedBbox.minX; const dy = py_bl - rotatedBbox.minY;
            const finalPoints = transformPoints(rotatedPoints, dx, dy, 0, 0, 0); // Util
            const pathString = pointsToSvgPath(finalPoints); // Util
            if (!pathString) { console.warn("No path string for:", p.originalName); return; }
            const partPath = document.createElementNS(svgNS, "path"); partPath.setAttribute("d", pathString); partPath.setAttribute("class", "svg-part-profile"); partPath.setAttribute("fill", "#cfe2ff"); partPath.setAttribute("stroke", "#052c65"); partPath.setAttribute("stroke-width", "0.7"); partPath.setAttribute("opacity", "0.85");
            const title = document.createElementNS(svgNS, "title"); title.textContent = `${p.originalName || p.partId} @ (${px_bl.toFixed(1)}, ${py_bl.toFixed(1)}) R:${rot}°`; partPath.appendChild(title);
            groupFlipY.appendChild(partPath);
            const label = document.createElementNS(svgNS, "text"); const labelX = px_bl + bboxWithSpacing.width / 2; const labelY = py_bl + bboxWithSpacing.height / 2; label.setAttribute("x", labelX.toString()); label.setAttribute("y", labelY.toString()); label.setAttribute("transform", `translate(0, ${sheetHeight}) scale(1, -1) translate(0, ${-sheetHeight + 2 * labelY})`); label.setAttribute("class", "svg-part-label"); let lt = p.partId || '?'; if (lt.startsWith('upload-')) lt = '...' + lt.substring(lt.length - 10); label.textContent = lt; label.appendChild(title.cloneNode(true)); groupFlipY.appendChild(label);
        });
    }
    targetDiv.appendChild(svg);
}*/
// --- END FUNCTION drawSheetLayout ---

// --- START FUNCTION drawSheetLayout ---
// DEZE FUNCTIE IS HIER GEDEFINIEERD en gebruikt utils
export function drawSheetLayout(targetDiv, sheetInfo, placementsOnSheet, visualOutputPlaceholder) {
    if (!targetDiv || !sheetInfo || typeof sheetInfo.width !== 'number' || typeof sheetInfo.height !== 'number') {
        console.error("Invalid input drawSheetLayout");
        targetDiv.innerHTML = '<p style="color:red;">Teken fout.</p>';
        if (visualOutputPlaceholder) visualOutputPlaceholder.style.display = 'none';
        return;
    }
    const svgNS = "http://www.w3.org/2000/svg";
    targetDiv.innerHTML = '';
    if (visualOutputPlaceholder) visualOutputPlaceholder.style.display = 'none';
    const sheetWidth = sheetInfo.width;
    const sheetHeight = sheetInfo.height;
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${sheetWidth} ${sheetHeight}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.style.maxWidth = `${sheetWidth}px`;
    svg.style.maxHeight = '500px';
    svg.style.display = 'block';
    svg.style.margin = 'auto';
    const styleDef = document.createElementNS(svgNS, "style");
    styleDef.textContent = `.svg-sheet{fill:#fdfdfe;stroke:#a0a0a0;stroke-width:1px;} .svg-part-profile{fill:#cfe2ff;stroke:#052c65;stroke-width:0.7px;opacity:0.85;} .svg-part-label{font-size:10px;font-family:sans-serif;fill:#333;text-anchor:middle;dominant-baseline:central;pointer-events:none;}`;
    svg.appendChild(styleDef);
    const groupFlipY = document.createElementNS(svgNS, "g");
    groupFlipY.setAttribute("transform", `translate(0, ${sheetHeight}) scale(1, -1)`);
    svg.appendChild(groupFlipY);
    const sheetRect = document.createElementNS(svgNS, "rect");
    sheetRect.setAttribute("x", "0");
    sheetRect.setAttribute("y", "0");
    sheetRect.setAttribute("width", sheetWidth.toString());
    sheetRect.setAttribute("height", sheetHeight.toString());
    sheetRect.setAttribute("class", "svg-sheet");
    groupFlipY.appendChild(sheetRect);

    if (placementsOnSheet?.length > 0) {
        placementsOnSheet.forEach((p) => {
            const prof = p.profile2d;
            const bboxWithSpacing = p.bbox;
            if (!prof || !prof.outer || !bboxWithSpacing || typeof bboxWithSpacing.x === 'undefined') {
                console.warn("Skip placement: no profile/bbox", p);
                return;
            }
            const origPoints = prof.outer;
            const px_bl = bboxWithSpacing.x;
            const py_bl = bboxWithSpacing.y;
            const rot = p.rotation || 0;
            const origBbox = calculateProfileBoundingBox(origPoints); // Util
            if (origBbox.width === 0 && origBbox.height === 0 && origPoints.length > 0) return;
            const rotCx = origBbox.minX + origBbox.width / 2;
            const rotCy = origBbox.minY + origBbox.height / 2;
            const rotatedPoints = transformPoints(origPoints, 0, 0, rot, rotCx, rotCy); // Util
            const rotatedBbox = calculateProfileBoundingBox(rotatedPoints); // Util
            if (rotatedBbox.width === 0 && rotatedBbox.height === 0 && rotatedPoints.length > 0) return;
            const dx = px_bl - rotatedBbox.minX;
            const dy = py_bl - rotatedBbox.minY;
            const finalPoints = transformPoints(rotatedPoints, dx, dy, 0, 0, 0); // Util
            const pathString = pointsToSvgPath(finalPoints); // Util
            if (!pathString) { console.warn("No path string for:", p.originalName); return; }
            const partPath = document.createElementNS(svgNS, "path");
            partPath.setAttribute("d", pathString);
            partPath.setAttribute("class", "svg-part-profile");
            partPath.setAttribute("fill", "#cfe2ff");
            partPath.setAttribute("stroke", "#052c65");
            partPath.setAttribute("stroke-width", "0.7");
            partPath.setAttribute("opacity", "0.85");
            const title = document.createElementNS(svgNS, "title");
            title.textContent = `${p.originalName || p.partId} @ (${px_bl.toFixed(1)}, ${py_bl.toFixed(1)}) R:${rot}°`;
            partPath.appendChild(title);
            groupFlipY.appendChild(partPath);
            
            // Tekenen van de Shapely polygon als extra pad in rood (als 'svg' veld aanwezig is)
            if (p.svg) {
                const redPath = document.createElementNS(svgNS, "path");
                redPath.setAttribute("d", p.svg);
                redPath.setAttribute("fill", "none");
                redPath.setAttribute("stroke", "red");
                redPath.setAttribute("stroke-width", "1");
                groupFlipY.appendChild(redPath);
                console.debug("Toegevoegde rode pad:", p.svg);
            }

            const label = document.createElementNS(svgNS, "text");
            const labelX = px_bl + bboxWithSpacing.width / 2;
            const labelY = py_bl + bboxWithSpacing.height / 2;
            label.setAttribute("x", labelX.toString());
            label.setAttribute("y", labelY.toString());
            label.setAttribute("transform", `translate(0, ${sheetHeight}) scale(1, -1) translate(0, ${-sheetHeight + 2 * labelY})`);
            label.setAttribute("class", "svg-part-label");
            let lt = p.partId || '?';
            if (lt.startsWith('upload-')) lt = '...' + lt.substring(lt.length - 10);
            label.textContent = lt;
            label.appendChild(title.cloneNode(true));
            groupFlipY.appendChild(label);
        });
    }
    targetDiv.appendChild(svg);
}
// --- END FUNCTION drawSheetLayout ---


// --- START FUNCTION displayNestingResults ---
export function displayNestingResults(placements = [], unplaced = [], statistics = {}, originalSheetsData = [], sheetStats = [], refs, state) {
    clearStatus(refs.statusMessagesDiv); // Gebruik geïmporteerde functie
    state.currentNestingResult = { placements, unplaced, statistics, sheetStats, sheetsData: originalSheetsData };
    state.currentSheetIndex = 0;
    // console.log("Displaying results. Placements:", placements?.length ?? 0);

    const placementsBySheet = defaultdict(() => []); // Gebruik helper uit utils
    if (placements?.length > 0) { placements.forEach(p => { if (p.sheetId) { placementsBySheet[p.sheetId].push(p); } }); }
    const usedSheetIds = Object.keys(placementsBySheet);
    const totalSheetsUsed = usedSheetIds.length;
    // console.log(`Grouped by ${totalSheetsUsed} sheets.`);

    // Update Samenvatting
    if (refs.summaryPlaceholder) refs.summaryPlaceholder.style.display = 'none';
    if (refs.summaryDetailsDiv) {
        refs.summaryDetailsDiv.innerHTML = '';
        let html = `<p><strong>Statistieken:</strong><br>Geplaatst: ${statistics?.totalPartsPlaced??'N/A'}<br>Niet Geplaatst: ${statistics?.totalPartsUnplaced??'N/A'}<br>Platen Gebruikt: ${totalSheetsUsed}</p>`;
        if (Array.isArray(sheetStats) && sheetStats.length > 0) {
            html += '<p><strong>Efficiëntie per plaat:</strong></p><ul>';
            sheetStats.forEach(s => { html += `<li>${s.sheetId}: ${s.efficiency}%</li>`; });
            html += '</ul>';
        }

        if (typeof statistics?.totalEfficiency === 'number') {
            html += `<p><strong>Totale efficiëntie:</strong> ${statistics.totalEfficiency}%</p>`;
        }
      
        if (unplaced?.length > 0) { html += `<p><strong>Niet Geplaatst:</strong></p><ul>`; unplaced.forEach(item => { const q = item.quantity || item.count || '?'; html += `<li>${item.originalName || item.id}: ${q}x</li>`; }); html += `</ul>`; }
        else if (statistics?.totalPartsPlaced > 0) { html += `<p style="color:green;"><strong>Alles geplaatst!</strong></p>`; }
        else { html += `<p style="color:orange;"><strong>Niets geplaatst.</strong></p>`; }
        refs.summaryDetailsDiv.innerHTML = html;
    }

    // Reset Navigatie en toon eerste plaat
    resetSheetNavigation(refs, state); // Roep lokale functie aan
    state.currentNestingResult = { placements, unplaced, statistics, sheetStats, sheetsData: originalSheetsData }; // Zet opnieuw na reset

    if (totalSheetsUsed > 0) {
        showSheet(0, refs, state); // Roep lokale functie aan
        if (refs.downloadSvgBtn) refs.downloadSvgBtn.disabled = false;
    } else {
        if (refs.visualOutputDiv && refs.visualOutputPlaceholder) { refs.visualOutputDiv.innerHTML = ''; refs.visualOutputPlaceholder.textContent = 'Geen plaatsingen.'; refs.visualOutputPlaceholder.style.display = 'block'; refs.visualOutputDiv.appendChild(refs.visualOutputPlaceholder); }
        if (refs.downloadSvgBtn) refs.downloadSvgBtn.disabled = true;
    }
}
// --- END FUNCTION displayNestingResults ---

// --- START FUNCTION updateSheetIndicator ---
// Deze is lokaal en wordt geëxporteerd
export function updateSheetIndicator(current, total, sheetIndicatorSpan) {
     if(sheetIndicatorSpan) {
          sheetIndicatorSpan.textContent = `Plaat ${current} / ${total}`;
     }
}
// --- END FUNCTION updateSheetIndicator ---

// --- START FUNCTION resetSheetNavigation ---
// Deze is lokaal en wordt geëxporteerd
export function resetSheetNavigation(refs, state) {
    if(refs.prevSheetBtn) refs.prevSheetBtn.disabled = true;
    if(refs.nextSheetBtn) refs.nextSheetBtn.disabled = true;
    if(refs.sheetIndicatorSpan) refs.sheetIndicatorSpan.textContent = 'Plaat 0 / 0';
    if(refs.downloadSvgBtn) refs.downloadSvgBtn.disabled = true;
    if(state) state.currentSheetIndex = 0;
}
// --- END FUNCTION resetSheetNavigation ---

// --- START FUNCTION showSheet ---
// Deze is lokaal en wordt geëxporteerd
export function showSheet(index, refs, state) {
    if (!state.currentNestingResult || !refs.visualOutputDiv) return;
    const placementsBySheet=defaultdict(()=>[]); state.currentNestingResult.placements.forEach(p=>{if(p.sheetId)placementsBySheet[p.sheetId].push(p);}); const usedSheetIds=Object.keys(placementsBySheet); const totalSheetsUsed=usedSheetIds.length;
    if(index<0||index>=totalSheetsUsed)return; // Blijf op huidige sheet

    state.currentSheetIndex=index; // Update state
    const sheetIdToShow=usedSheetIds[state.currentSheetIndex];
    const sheetInfo=findSheetInfoById(sheetIdToShow,state.currentNestingResult.sheetsData); // Gebruik helper uit utils

    if (sheetInfo) {
         // Roep lokale drawSheetLayout aan
         drawSheetLayout(refs.visualOutputDiv, sheetInfo, placementsBySheet[sheetIdToShow], refs.visualOutputPlaceholder);
         updateSheetIndicator(state.currentSheetIndex + 1, totalSheetsUsed, refs.sheetIndicatorSpan); // Gebruik lokale functie
         if (refs.prevSheetBtn) refs.prevSheetBtn.disabled = state.currentSheetIndex === 0; // Update knoppen
         if (refs.nextSheetBtn) refs.nextSheetBtn.disabled = state.currentSheetIndex === totalSheetsUsed - 1;
         if (refs.downloadSvgBtn) refs.downloadSvgBtn.disabled = false;
    } else { console.error("Sheet info not found for index:",index,"ID:",sheetIdToShow); refs.visualOutputDiv.innerHTML='<p style="color:red;">Fout: Plaat info.</p>'; if(refs.downloadSvgBtn)refs.downloadSvgBtn.disabled=true;}
}
// --- END FUNCTION showSheet ---