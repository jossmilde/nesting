// Bestand: public/js/main.js

// --- Imports ---
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
// Importeer functies uit andere modules
import { showStatus, clearStatus, calculateProfileBoundingBox, pointsToSvgPath, transformPoints, defaultdict, findSheetInfoById } from './utils.js';
import { render3DPreview, cleanupThreeInstance } from './threeManager.js';
import { addManualSheetDefinition, removeManualSheetDefinition, addFileToTable, displayNestingResults, drawSheetLayout, updateSheetIndicator, resetSheetNavigation, showSheet } from './domManager.js';

// --- Element Referenties ---
const uploadForm = document.getElementById('upload-form');
const fileInput = document.getElementById('file-input');
const uploadButton = document.getElementById('upload-button');
const statusMessagesDiv = document.getElementById('status-messages');
const manualSheetsContainer = document.getElementById('manual-sheet-definitions');
const addManualSheetButton = document.getElementById('add-manual-sheet-btn');
const noManualSheetsMsg = document.getElementById('no-manual-sheets-msg');
const uploadedFilesListDiv = document.getElementById('uploaded-files-list');
const uploadedFilesTable = uploadedFilesListDiv.querySelector('table');
const uploadedFilesTBody = uploadedFilesTable?.querySelector('tbody');
const noFilesMessage = document.getElementById('no-files-message');
const startNestingBtn = document.getElementById('start-nesting-btn');
const nestProgressBar = document.getElementById('nest-progress');
const currentYearSpan = document.getElementById('current-year');
const partToPartDistanceInput = document.getElementById('part-to-part-distance');
const partToSheetDistanceInput = document.getElementById('part-to-sheet-distance');
const allowRotationSelect = document.getElementById('allow-rotation');
const allowMirroringCheckbox = document.getElementById('allow-mirroring');
const nestingStrategySelect = document.getElementById('nesting-strategy');
const nestingAlgorithmSelect = document.getElementById('nesting-algorithm');
const enableDebugCheckbox = document.getElementById('enable-debug');
const enableTimingCheckbox = document.getElementById('enable-timing');
const visualOutputDiv = document.getElementById('visual-output');
const visualOutputPlaceholder = document.getElementById('visual-output-placeholder');
const summaryOutputDiv = document.getElementById('summary-output');
const summaryPlaceholder = document.getElementById('summary-placeholder');
const summaryDetailsDiv = document.getElementById('summary-details');
const prevSheetBtn = document.getElementById('prev-sheet-btn');
const nextSheetBtn = document.getElementById('next-sheet-btn');
const sheetIndicatorSpan = document.getElementById('sheet-indicator');
const downloadSvgBtn = document.getElementById('download-svg-btn');

// Bundel refs voor makkelijker doorgeven
const elementRefs = {
    statusMessagesDiv, manualSheetsContainer, noManualSheetsMsg,
    uploadedFilesTBody, uploadedFilesTable, noFilesMessage,
    visualOutputDiv, visualOutputPlaceholder, summaryDetailsDiv, summaryPlaceholder,
    prevSheetBtn, nextSheetBtn, sheetIndicatorSpan, downloadSvgBtn,
    partToPartDistanceInput, partToSheetDistanceInput, allowRotationSelect,
    allowMirroringCheckbox, nestingStrategySelect, nestingAlgorithmSelect,
    enableDebugCheckbox, enableTimingCheckbox
};

// --- Globale staat ---
let uploadedPartsData = {};
let threeInstances = {};
let manualSheetCounter = 0;
let currentNestingResult = null;
let currentSheetIndex = 0;

// Bundel state in één object
let appState = {
    uploadedPartsData: uploadedPartsData,
    threeInstances: threeInstances,
    manualSheetCounter: manualSheetCounter,
    currentNestingResult: currentNestingResult,
    currentSheetIndex: currentSheetIndex
};

let progressTimer = null;
function startProgress() {
    if (!nestProgressBar) return;
    nestProgressBar.value = 0;
    nestProgressBar.style.display = 'block';
    progressTimer = setInterval(() => {
        nestProgressBar.value = (nestProgressBar.value + 1) % 100;
    }, 100);
}

function stopProgress() {
    if (!nestProgressBar) return;
    if (progressTimer) clearInterval(progressTimer);
    progressTimer = null;
    nestProgressBar.style.display = 'none';
}


// --- DATA VERZAMEL FUNCTIE (hoort logisch hier) ---
function collectNestingJobData() {
     console.log("[Collect] Verzamelen nesting job data START...");
     try {
         const jobData = { parts: [], sheets: [], parameters: {} };
         let hasError = false;

         // Verzamel Onderdelen
         console.log("[Collect] Start verzamelen Onderdelen...");
         if (!elementRefs.uploadedFilesTBody) { showStatus(elementRefs.statusMessagesDiv, "Fout: Tabel niet gevonden.", "error"); return null; }
         Object.keys(appState.uploadedPartsData).forEach(serverFilename => { // Gebruik appState
             if (hasError) return;
             const partInfo = appState.uploadedPartsData[serverFilename];
             const quantityInput = document.getElementById(`quantity-${serverFilename}`);
             const quantity = parseInt(quantityInput?.value || '0', 10);
             const selectedFaceId = partInfo.selectedFaceId || partInfo.defaultFaceId;
             const profileData = partInfo.profiles2d ? partInfo.profiles2d[selectedFaceId] : null;
             if (partInfo && quantity > 0 && profileData) {
                 jobData.parts.push({ id:serverFilename, originalName:partInfo.originalName, quantity:quantity, thickness:partInfo.thickness, selectedFaceId:selectedFaceId, profile2d:profileData });
             } else if (partInfo && quantity > 0) {
                 const eMsg=`Deel ${partInfo.originalName}: geen profiel voor vlak ${selectedFaceId}.`; console.warn(eMsg); showStatus(elementRefs.statusMessagesDiv, eMsg,"error"); hasError = true;
             }
         });
         if (hasError) { console.log("[Collect] Fout bij verzamelen onderdelen."); return null; }
         console.log(`[Collect] ${jobData.parts.length} onderdelen toegevoegd.`);

         // Verzamel Manuele Platen
         console.log("[Collect] Start verzamelen Manuele Platen...");
         let manualSheetsFound = 0;
         if (elementRefs.manualSheetsContainer) {
             const entries = elementRefs.manualSheetsContainer.querySelectorAll('.manual-sheet-entry');
             entries.forEach((entry) => {
                 const idSuffix = entry.id.replace('manual-sheet-','');
                 const wEl=entry.querySelector(`#manual-width-${idSuffix}`); const hEl=entry.querySelector(`#manual-height-${idSuffix}`); const tEl=entry.querySelector(`#manual-thickness-${idSuffix}`); const qEl=entry.querySelector(`#manual-quantity-${idSuffix}`);
                 if (wEl&&hEl&&tEl&&qEl) { const w=parseFloat(wEl.value)||0; const h=parseFloat(hEl.value)||0; const t=parseFloat(tEl.value); const q=parseInt(qEl.value,10)||0; if(w>0&&h>0&&!isNaN(t)&&q>0){ jobData.sheets.push({id:`manual_${idSuffix}`,source:'manual',width:w,height:h,thickness:t,quantity:q}); manualSheetsFound++; } else { console.warn(`[Collect] Invalid values for manual sheet ${idSuffix}.`); }
                 } else { console.warn(`[Collect] Inputs not found in entry ${entry.id}.`); }
             });
         }
         console.log(`[Collect] ${manualSheetsFound} manuele platen toegevoegd.`);

         // Verzamel Platen van Onderdelen
         console.log("[Collect] Start verzamelen Platen van Onderdelen...");
         let partSheetsFound = 0;
         if (elementRefs.uploadedFilesTBody) {
             const rows = elementRefs.uploadedFilesTBody.querySelectorAll('tr');
             rows.forEach((row) => {
                 if(hasError)return; const cb=row.querySelector('.use-as-sheet-checkbox'); const qIn=row.querySelector('.sheet-quantity-input');
                 if(cb?.checked && qIn){
                     const srv=row.id.replace('row-',''); const pData=appState.uploadedPartsData[srv]; const qty=parseInt(qIn.value,10)||0;
                     const sheetProf=pData?.profiles2d?.[pData.defaultFaceId];
                     if(pData&&qty>0&&sheetProf&&sheetProf.outer){ const bbox=calculateProfileBoundingBox(sheetProf.outer); jobData.sheets.push({id:`part_${srv}`,source:'part',originalName:pData.originalName,width:bbox.width,height:bbox.height,thickness:pData.thickness,quantity:qty}); partSheetsFound++; }
                     else if(pData&&qty>0){ const eMsg=`Deel ${pData.originalName} als plaat: geen default profiel.`; console.warn(eMsg); showStatus(elementRefs.statusMessagesDiv, eMsg,"error"); hasError=true; }
                }
             });
         }
         if (hasError) return null;
         console.log(`[Collect] ${partSheetsFound} platen van onderdelen toegevoegd.`);

         // Verzamel Parameters
         console.log("[Collect] Verzamelen parameters...");
       jobData.parameters={partToPartDistance:parseFloat(elementRefs.partToPartDistanceInput?.value??5),partToSheetDistance:parseFloat(elementRefs.partToSheetDistanceInput?.value??10),allowRotation:elementRefs.allowRotationSelect?.value??"2",allowMirroring:elementRefs.allowMirroringCheckbox?.checked??false,strategy:elementRefs.nestingStrategySelect?.value??"balanced",nestingStrategy:elementRefs.nestingAlgorithmSelect?.value??"DEFAULT"};
        jobData.debug = elementRefs.enableDebugCheckbox?.checked ?? false;
        jobData.timing = elementRefs.enableTimingCheckbox?.checked ?? false;

         // Validatie
         console.log("[Collect] Start validatie...");
         if (jobData.parts.length === 0) { showStatus(elementRefs.statusMessagesDiv, "Geen onderdelen geselecteerd.", "error"); return null; }
         if (jobData.sheets.length === 0) { showStatus(elementRefs.statusMessagesDiv, "Geen platen gedefinieerd.", "error"); return null; }

         console.log("Nesting job data verzameld:", JSON.stringify(jobData));
         return jobData;

    } catch (error) {
         console.error("[Collect] UNEXPECTED ERROR in collectNestingJobData:", error);
         showStatus(elementRefs.statusMessagesDiv, `Interne fout bij data verzamelen: ${error.message}`, 'error');
         return null;
    }
}
// --- EINDE collectNestingJobData ---


// --- Event Handler Functies ---

// Upload Submit Handler (NIEUW GEDEFINIEERD)
async function handleUploadSubmit(event) {
    event.preventDefault();
    clearStatus(elementRefs.statusMessagesDiv);
    showStatus(elementRefs.statusMessagesDiv, 'Bezig met uploaden & verwerken...', 'info');
    if (uploadButton) uploadButton.disabled = true;

    const files = fileInput.files;
    if (!files || files.length === 0) {
        showStatus(elementRefs.statusMessagesDiv, 'Selecteer bestanden.', 'error');
        if (uploadButton) uploadButton.disabled = false;
        return;
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) { formData.append('files[]', files[i]); }

    try {
        const response = await fetch('/upload', { method: 'POST', body: formData });
        const isJson = response.headers.get('content-type')?.includes('application/json');
        const data = isJson ? await response.json() : null;
        if (!response.ok) { const errorMsg = (data && data.message) || response.statusText || `HTTP ${response.status}`; throw new Error(errorMsg); }
        handleUploadSuccessResponse(data); // Roep success handler aan
    } catch (error) {
        handleUploadErrorResponse(error); // Roep error handler aan
    } finally {
        if (uploadButton) uploadButton.disabled = false;
    }
}

// Upload Success Handler (roept sequentiële UI update aan)
function handleUploadSuccessResponse(data) {
     let msg=`<strong>Verwerking voltooid.</strong>`; let details="<ul>"; let ok=true;
     let resultsToProcess = [];

     if (data.results?.length > 0) {
         data.results.forEach(result => {
             const o=result.originalName; const s=result.filename; const p=result.processingResult;
             if (!s) { console.error("Resultaat mist serverFilename:", result); details+=`<li>${o||'Onbekend'}: Fout!</li>`; ok=false; return; }
             if (p?.success) {
                 // Update globale state
                 appState.uploadedPartsData[s] = { originalName:o, serverFilename:s, meshData:p.mesh, facesInfo:p.facesInfo||[], defaultFaceId:p.defaultFaceId||null, secondLargestFaceId:p.secondLargestFaceId||null, thickness:p.thickness, selectedFaceId:p.defaultFaceId||null, profiles2d:p.profiles2d||{} };
                 const tStr=typeof p.thickness==='number'?` D:${p.thickness.toFixed(2)}mm`:''; const profOk=p.profiles2d&&Object.keys(p.profiles2d).length>0;
                 details+=`<li>${o}: OK ${p.mesh?'(Mesh ✓)':'(X Mesh!)'} (${p.facesInfo?.length||0} vlk)${tStr} ${profOk?'(Prof ✓)':'(X Prof!)'}</li>`;
                 resultsToProcess.push(result);
             } else { details+=`<li>${o}: <span style="color:red;">Fout</span> - ${p?.error||'Onbekend'}</li>`; ok=false; }
         });
     } else { msg+="<br>Geen resultaten."; ok=false; }
     details+="</ul>";
     showStatus(elementRefs.statusMessagesDiv, msg+details, ok ? 'success' : 'error');

     // Start sequentiële UI update
     if (resultsToProcess.length > 0) {
         currentUploadResultIndex = 0; // Reset index
         processUploadResultsSequentially(resultsToProcess); // Start de ketting
     }
 }

// Sequentiële UI updater (verplaatst naar hier)
let currentUploadResultIndex = 0;
let uploadProcessingDelay = 150; // ms

function processUploadResultsSequentially(results) {
    if (currentUploadResultIndex >= results.length) {
        console.log("Alle UI updates voor upload voltooid.");
        currentUploadResultIndex = 0; // Reset voor volgende upload
        return;
    }
    const result = results[currentUploadResultIndex];
    // console.log(`Sequentially processing UI for: ${result.originalName}`); // Minder logs
    try {
        // Roep addFileToTable aan (uit domManager), geef state/refs mee
        addFileToTable(result, appState.uploadedPartsData, appState.threeInstances, elementRefs.uploadedFilesTBody, elementRefs.uploadedFilesTable, elementRefs.noFilesMessage);
    } catch (tableErr) {
        console.error("Fout tijdens sequentiële addFileToTable!", tableErr);
        showStatus(elementRefs.statusMessagesDiv, `Fout bij UI update voor ${result.originalName}: ${tableErr.message}`, 'error');
    }
    currentUploadResultIndex++;
    setTimeout(() => { processUploadResultsSequentially(results); }, uploadProcessingDelay);
}

// Upload Error Handler
function handleUploadErrorResponse(error) {
    console.error('Upload Fout:', error);
    showStatus(elementRefs.statusMessagesDiv, `<strong>Upload/Verwerking mislukt:</strong><br>${error.message}`, 'error');
}

// Start Nesting Handler
async function handleStartNestingClick() {
    console.log("[main.js] Start Nesting knop geklikt.");
    clearStatus(elementRefs.statusMessagesDiv);
    let jobData = null;
    try { jobData = collectNestingJobData(); } // Roep lokale verzamel functie aan
    catch (collectError) { console.error("Fout verzamelen:", collectError); showStatus(elementRefs.statusMessagesDiv, `Fout verzamelen: ${collectError.message}`, "error"); return; }
    if (!jobData) { console.log("Nesting gestopt, data ongeldig."); return; }

    showStatus(elementRefs.statusMessagesDiv, "Nesting versturen...", "info");
    if(startNestingBtn) startNestingBtn.disabled = true;
    startProgress();
    if (elementRefs.visualOutputDiv && elementRefs.visualOutputPlaceholder) { elementRefs.visualOutputDiv.innerHTML = ''; elementRefs.visualOutputDiv.appendChild(elementRefs.visualOutputPlaceholder); elementRefs.visualOutputPlaceholder.textContent = 'Nesting bezig...'; elementRefs.visualOutputPlaceholder.style.display = 'block'; }
    if (elementRefs.summaryDetailsDiv) elementRefs.summaryDetailsDiv.innerHTML = ''; if (elementRefs.summaryPlaceholder) elementRefs.summaryPlaceholder.style.display = 'block';
    resetSheetNavigation(elementRefs, appState); // Gebruik helper uit domManager

    try {
        const response = await fetch('/nest', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(jobData) });
        const result = await response.json();
        if (!response.ok || result.success === false) { throw new Error(result.message || `Serverfout: ${response.statusText}`); }
        console.log("[main.js] Server response /nest:", result);
        // Roep display functie aan (uit domManager), geef refs en state mee
        displayNestingResults(result.placements, result.unplaced, result.statistics, jobData.sheets, elementRefs, appState);
        showStatus(elementRefs.statusMessagesDiv, `Nesting voltooid: ${result.message || 'Klaar.'}`, "success");
    } catch (error) {
        console.error("[main.js] Fout bij /nest call:", error);
        handleUploadErrorResponse(error); // Gebruik error handler
        if (elementRefs.visualOutputPlaceholder) elementRefs.visualOutputPlaceholder.textContent = 'Fout bij nesting.';
        if (elementRefs.visualOutputDiv && elementRefs.visualOutputDiv.children.length === 1 && elementRefs.visualOutputDiv.firstChild === elementRefs.visualOutputPlaceholder && elementRefs.visualOutputPlaceholder) { elementRefs.visualOutputPlaceholder.style.display = 'block';} else if(elementRefs.visualOutputDiv && elementRefs.visualOutputPlaceholder){elementRefs.visualOutputDiv.innerHTML = ''; elementRefs.visualOutputDiv.appendChild(elementRefs.visualOutputPlaceholder);}
    } finally {
        if(startNestingBtn) startNestingBtn.disabled = false;
        stopProgress();
    }
}


// --- EVENT LISTENERS KOPPELEN ---
console.log("Attaching event listeners...");

if (uploadForm) {
    uploadForm.addEventListener('submit', handleUploadSubmit); // Koppel de handler
} else { console.error("Upload form not found!"); }

if (addManualSheetButton) {
    addManualSheetButton.addEventListener('click', () => {
        // Roep functie uit domManager aan, update teller in appState
        appState.manualSheetCounter = addManualSheetDefinition(elementRefs.manualSheetsContainer, elementRefs.noManualSheetsMsg, appState.manualSheetCounter);
    });
} else { console.error("Add manual sheet button not found!"); }

if (elementRefs.uploadedFilesTBody) {
    // Click listener voor remove en load preview (delegated)
     elementRefs.uploadedFilesTBody.addEventListener('click', (event) => {
         // Verwijder knop
         if (event.target.classList.contains('remove-part-btn')) { try { const b=event.target; const srv=b.dataset.filename; const row=b.closest('tr'); if(srv&&row){ const pId=`preview-${srv}`; cleanupThreeInstance(appState.threeInstances, pId); delete appState.uploadedPartsData[srv]; row.remove(); if(elementRefs.uploadedFilesTBody.children.length===0&&elementRefs.noFilesMessage&&elementRefs.uploadedFilesTable){ elementRefs.noFilesMessage.style.display='block'; elementRefs.uploadedFilesTable.style.display='none'; }} } catch(e) { console.error("Fout bij verwijderen:", e); } }
         // Load Preview Knop
         else if (event.target.classList.contains('load-preview-btn')) { const b=event.target; const tId=b.dataset.targetId; const srv=b.dataset.filename; if(!tId||!srv)return; const pData=appState.uploadedPartsData[srv]; if(!pData||!pData.meshData){ console.error("Geen mesh data", srv); const ph=document.getElementById(tId); if(ph)ph.innerHTML='Fout!';return; } let f1=null,f2=null; if(pData.facesInfo?.length>0){ f1=pData.facesInfo.find(f=>f.id===pData.defaultFaceId); f2=pData.facesInfo.find(f=>f.id===pData.secondLargestFaceId); } b.textContent="Laden..."; b.disabled=true; const ph=document.getElementById(tId); if(ph)ph.innerHTML='<i>Laden...</i>'; setTimeout(()=>{ try{ render3DPreview(appState.threeInstances,tId,pData.meshData,f1,f2); b.textContent="Geladen";}catch(e){console.error("Fout renderPreview:",e);if(ph)ph.innerHTML='Render Fout!';b.textContent="Fout";b.disabled=false;} }, 0); }
     });
     // Change listener voor checkbox/select
     elementRefs.uploadedFilesTBody.addEventListener('change', (event) => { try { if (event.target.classList.contains('use-as-sheet-checkbox')) { const qIn=document.getElementById(event.target.dataset.quantityInputId); if(qIn) qIn.style.display = event.target.checked ? 'block' : 'none'; } else if (event.target.tagName === 'SELECT' && event.target.id.startsWith('face-select-')) { const faceId=event.target.value; const serverFilename=event.target.id.replace('face-select-',''); if(appState.uploadedPartsData[serverFilename]) appState.uploadedPartsData[serverFilename].selectedFaceId = faceId; } } catch (e){ console.error("Tabel change listener fout:", e); } });
} else { console.warn("Tbody not found!"); }

// Start Nesting knop Listener
if (startNestingBtn) {
     startNestingBtn.addEventListener('click', handleStartNestingClick); // Koppel handler
} else { console.error("Start nesting button not found!"); }

// Plaat Navigatie Listeners
if (prevSheetBtn) { prevSheetBtn.addEventListener('click', () => { if (appState.currentNestingResult) { showSheet(appState.currentSheetIndex - 1, elementRefs, appState); } }); } else { console.error("Prev sheet button not found!"); }
if (nextSheetBtn) { nextSheetBtn.addEventListener('click', () => { if (appState.currentNestingResult) { showSheet(appState.currentSheetIndex + 1, elementRefs, appState); } }); } else { console.error("Next sheet button not found!"); }

// SVG Download Listener
if (downloadSvgBtn) { downloadSvgBtn.addEventListener('click', () => { console.log("Download SVG clicked"); if(!elementRefs.visualOutputDiv){showStatus(elementRefs.statusMessagesDiv,"Fout: Resultaatgebied niet vinden.","error");return;} const svgElement=elementRefs.visualOutputDiv.querySelector('svg');if(!svgElement){showStatus(elementRefs.statusMessagesDiv,"Fout: Geen SVG gevonden.","error");return;} try{const serializer=new XMLSerializer();let svgString=serializer.serializeToString(svgElement);const svgXML='<?xml version="1.0" standalone="no"?>\r\n'; if(!svgString.includes('xmlns="http://www.w3.org/2000/svg"')){svgString=svgString.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');} svgString=svgXML+svgString; const blob=new Blob([svgString],{type:'image/svg+xml;charset=utf-8'}); const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; const fileName=`nesting_sheet_${appState.currentSheetIndex+1}.svg`; link.download=fileName; document.body.appendChild(link); link.click(); document.body.removeChild(link); URL.revokeObjectURL(url); console.log(`SVG ${fileName} download gestart.`); showStatus(elementRefs.statusMessagesDiv,`SVG ${fileName} wordt gedownload...`,'info');} catch(err){console.error("Fout SVG download:",err);showStatus(elementRefs.statusMessagesDiv,`Fout SVG export: ${err.message}`,"error");}}); }
 else { console.error("Download SVG button not found!"); }


// --- Initialisatie ---
if (currentYearSpan) {
    currentYearSpan.textContent = new Date().getFullYear();
}
// Roep reset aan met correcte naam en argumenten
resetSheetNavigation(elementRefs, appState);
console.log("Main script initialized.");