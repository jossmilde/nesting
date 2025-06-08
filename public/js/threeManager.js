// Bestand: public/js/threeManager.js
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// --- START FUNCTION cleanupThreeInstance ---
export function cleanupThreeInstance(threeInstances, targetElementId) {
    if (threeInstances && threeInstances[targetElementId]) {
        const instance = threeInstances[targetElementId];
        if (instance.animationFrameId) { cancelAnimationFrame(instance.animationFrameId); }
        if (instance.resizeObserver) { try { instance.resizeObserver.disconnect(); } catch (e) {} }
        if (instance.renderer) {
            instance.renderer.dispose();
            const container = document.getElementById(targetElementId);
            if (container && instance.renderer.domElement.parentNode === container) {
                container.removeChild(instance.renderer.domElement);
            }
        }
        delete threeInstances[targetElementId];
        console.log(`Cleaned Three instance: ${targetElementId}`);
    }
}
// --- END FUNCTION cleanupThreeInstance ---

// --- START FUNCTION render3DPreview ---
export function render3DPreview(threeInstances, targetElementId, meshData, largestFaceInfo = null, secondLargestFaceInfo = null) {
    cleanupThreeInstance(threeInstances, targetElementId); // Roep cleanup aan met state object
    const container = document.getElementById(targetElementId);
    if (!container) { console.error(`Container #${targetElementId} not found.`); return; }
    while (container.firstChild) { container.removeChild(container.firstChild); }

    try {
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0xf0f0f0);
        const width = container.clientWidth; const height = container.clientHeight;
        if (width <= 0 || height <= 0) { setTimeout(() => render3DPreview(threeInstances, targetElementId, meshData, largestFaceInfo, secondLargestFaceInfo), 150); return; }
        const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 5000);
        const renderer = new THREE.WebGLRenderer({ antialias: true }); renderer.setSize(width, height); renderer.setPixelRatio(window.devicePixelRatio); container.appendChild(renderer.domElement);
        const geometry = new THREE.BufferGeometry(); if (!meshData?.vertices || !meshData?.indices) throw new Error("Invalid meshData");
        const vertices = new Float32Array(meshData.vertices); geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3)); const indices = vertices.length / 3 > 65535 ? new Uint32Array(meshData.indices) : new Uint16Array(meshData.indices); geometry.setIndex(new THREE.BufferAttribute(indices, 1)); geometry.computeVertexNormals(); geometry.computeBoundingBox(); if (!geometry.boundingBox) throw new Error("No bbox"); const boxCenter = new THREE.Vector3(); geometry.boundingBox.getCenter(boxCenter); const boxSize = new THREE.Vector3(); geometry.boundingBox.getSize(boxSize); const objectSize = Math.max(boxSize.x, boxSize.y, boxSize.z, 1.0);
        const distance = Math.max(50, Math.min(objectSize * 1.5, 2000)); camera.position.set(boxCenter.x, boxCenter.y + distance * 0.6, boxCenter.z + distance); camera.lookAt(boxCenter);
        const material = new THREE.MeshStandardMaterial({ color: 0xcccccc, metalness: 0.2, roughness: 0.8, side: THREE.DoubleSide }); const mesh = new THREE.Mesh(geometry, material); scene.add(mesh);
        try { const edges = new THREE.EdgesGeometry(geometry, 1); const lineMaterial = new THREE.LineBasicMaterial({ color: 0x111111 }); const lineSegments = new THREE.LineSegments(edges, lineMaterial); scene.add(lineSegments); } catch (e) { console.warn(`Edges error: ${e}`); }
        const arrowL = Math.max(10, objectSize * 0.3), headL = Math.max(3, arrowL * 0.2), headW = Math.max(2, headL * 0.6);
        const validL = largestFaceInfo && Array.isArray(largestFaceInfo.centroid) && largestFaceInfo.centroid.length === 3 && Array.isArray(largestFaceInfo.normal) && largestFaceInfo.normal.length === 3; if (validL) { try { const o = new THREE.Vector3().fromArray(largestFaceInfo.centroid); const d = new THREE.Vector3().fromArray(largestFaceInfo.normal).normalize(); if (d.lengthSq() < 0.001) throw new Error("Norm0"); const aR = new THREE.ArrowHelper(d, o, arrowL, 0xff0000, headL, headW); scene.add(aR); } catch (e) { console.error("Red arrow err", e); } }
        const validS = secondLargestFaceInfo && Array.isArray(secondLargestFaceInfo.centroid) && secondLargestFaceInfo.centroid.length === 3 && Array.isArray(secondLargestFaceInfo.normal) && secondLargestFaceInfo.normal.length === 3; if (validS) { try { const o = new THREE.Vector3().fromArray(secondLargestFaceInfo.centroid); const d = new THREE.Vector3().fromArray(secondLargestFaceInfo.normal).normalize(); if (d.lengthSq() < 0.001) throw new Error("Norm0"); const aG = new THREE.ArrowHelper(d, o, arrowL, 0x00cc00, headL, headW); scene.add(aG); } catch (e) { console.error("Green arrow err", e); } }
        scene.add(new THREE.AmbientLight(0xffffff, 0.8)); const dl1 = new THREE.DirectionalLight(0xffffff, 1.0); dl1.position.set(1, 1.5, 1); scene.add(dl1); const dl2 = new THREE.DirectionalLight(0xffffff, 0.6); dl2.position.set(-1, -0.5, -1); scene.add(dl2);
        const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.dampingFactor = 0.1; controls.target.copy(boxCenter); controls.update();
        let afid = null; const instanceInfo = { renderer: renderer, animationFrameId: null, resizeObserver: null }; function animate() { afid = requestAnimationFrame(animate); instanceInfo.animationFrameId = afid; if (controls.update()) { renderer.render(scene, camera); } } controls.addEventListener('change', () => {}); animate();
        const ro = new ResizeObserver(ents => { for (let e of ents) { requestAnimationFrame(() => { const { width: nw, height: nh } = e.contentRect; if (instanceInfo.renderer && nw > 0 && nh > 0) { camera.aspect = nw / nh; camera.updateProjectionMatrix(); instanceInfo.renderer.setSize(nw, nh); } }); } });
        ro.observe(container); instanceInfo.resizeObserver = ro;
        threeInstances[targetElementId] = instanceInfo; // Sla op in meegegeven state object
    } catch (e) { console.error(`Render Error #${targetElementId}:`, e); container.textContent = 'Render Fout!'; container.style.color = 'red'; }
}
// --- END FUNCTION render3DPreview ---