/**
 * SENTINEL V7: SUBTERRANEAN SWARM & NALA MANAGEMENT (nala_manager.js)
 * Manages Live Cartography, Swarm Worker, and HUD Injection.
 */

const NALA_CONFIG = {
    color: '#00d2ff',
    alertColor: '#ef4444',
    weight: 2,
    alertWeight: 5,
    bounds: [18.85, 72.75, 19.35, 73.10]
};

const API_BASE = "http://127.0.0.1:8000";

let nalaMesh = {};
window.activeWorker = null;

function getMetaContent(name) {
    const el = document.querySelector(`meta[name="${name}"]`);
    return el && el.getAttribute('content') ? el.getAttribute('content').trim() : '';
}

function resolveApiRoot() {
    return (getMetaContent('sentinel-api-base') || API_BASE).replace(/\/$/, '');
}

window.SENTINEL_JWT_TOKEN = null;

async function initializeSecureSession() {
    console.log("[SENTINEL] Initializing secure JWT session...");
    try {
        const response = await fetch(`${resolveApiRoot()}/api/v1/auth/session`);
        const data = await response.json();
        window.SENTINEL_JWT_TOKEN = data.token;
        console.log("[SENTINEL] Secure session established.");
    } catch (e) {
        console.error("[SENTINEL] Failed to initialize secure session", e);
    }
}

/**
 * Request header builder — uses JWT Bearer token and Anti-Replay headers.
 */
async function sentinelBuildSignedHeaders(method, path, bodyString) {
    if (!window.SENTINEL_JWT_TOKEN) {
        console.warn('[SENTINEL] Secure session not initialized. Attempting recovery...');
        await initializeSecureSession();
    }
    
    const ts = Math.floor(Date.now() / 1000).toString();
    const nonce = crypto.randomUUID();
    
    return {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + window.SENTINEL_JWT_TOKEN,
        'X-Timestamp': ts,
        'X-Nonce': nonce
    };
}

/**
 * AGENT TASK 1: THE CARTOGRAPHIC CRAWLER
 */
async function fetchLiveNalaMesh(map, engine = 'leaflet') {
    console.log("[NALA] Crawling Overpass API for drainage mesh...");
    const query = `[out:json][timeout:25];(way["waterway"="drain"](${NALA_CONFIG.bounds.join(',')});way["waterway"="canal"](${NALA_CONFIG.bounds.join(',')}););out geom;`;

    try {
        const response = await fetch('https://overpass-api.de/api/interpreter', {
            method: 'POST',
            body: query
        });
        const data = await response.json();

        data.elements.forEach(el => {
            if (el.type === 'way' && el.geometry) {
                const coords = el.geometry.map(p => [p.lat, p.lon]);

                if (engine === 'leaflet') {
                    const poly = L.polyline(coords, {
                        color: NALA_CONFIG.color,
                        weight: NALA_CONFIG.weight,
                        opacity: 0.4,
                        className: 'nala-segment'
                    }).addTo(map);
                    nalaMesh[el.id] = poly;
                } else if (engine === 'maplibre') {
                    const sourceId = `nala-${el.id}`;
                    map.addSource(sourceId, {
                        'type': 'geojson',
                        'data': {
                            'type': 'Feature',
                            'properties': {},
                            'geometry': {
                                'type': 'LineString',
                                'coordinates': el.geometry.map(p => [p.lon, p.lat])
                            }
                        }
                    });
                    map.addLayer({
                        'id': sourceId,
                        'type': 'line',
                        'source': sourceId,
                        'layout': { 'line-join': 'round', 'line-cap': 'round' },
                        'paint': { 'line-color': NALA_CONFIG.color, 'line-width': NALA_CONFIG.weight, 'line-opacity': 0.4 }
                    });
                    nalaMesh[el.id] = sourceId;
                }
            }
        });
        console.log(`[NALA] ${data.elements.length} segments rendered.`);
    } catch (e) {
        console.error("[NALA] Overpass fetch failed", e);
    }
}

/**
 * AGENT TASK 2 & 3: SWARM INTEL & UI INTEGRATION
 */
function initSwarmIntelligence(map, engine = 'leaflet') {
    console.log("[SWARM] Deploying nala_worker.js...");
    window.activeWorker = new Worker('nala_worker.js');

    window.activeWorker.onmessage = function(e) {
        if (e.data && e.data.type === 'SIMULATION_RESULT') {
            const results = e.data.results;
            if (document.getElementById('pinn-manning-n')) document.getElementById('pinn-manning-n').innerText = results.manning_roughness_n;
            if (document.getElementById('pinn-delta-v')) document.getElementById('pinn-delta-v').innerText = results.wave_velocity_delta_m_s + " m/s";
            if (document.getElementById('pinn-delta-d')) document.getElementById('pinn-delta-d').innerText = results.delta_inundation_depth_m + " m";
            return;
        }

        const { totalNodes, latency, chokeClusters, biLstmPacket } = e.data;

        updateSwarmHUD(totalNodes, latency, chokeClusters.length);

        chokeClusters.forEach(cluster => {
            const nearestId = findNearestNala(cluster.lat, cluster.lng);
            if (nearestId && nalaMesh[nearestId]) {
                triggerNalaAlert(nearestId, engine, map);
            }
        });

        syncSwarmWithBackend(biLstmPacket);
    };
}

async function syncSwarmWithBackend(packet) {
    try {
        const path = '/api/v1/telemetry/swarm_aggregation';
        const bodyString = typeof packet === 'string' ? packet : JSON.stringify(packet);
        const headers = await sentinelBuildSignedHeaders('POST', path, bodyString);
        const response = await fetch(`${resolveApiRoot()}${path}`, {
            method: 'POST',
            headers,
            body: bodyString
        });

        if (response.ok) {
            const syncStatus = document.getElementById('swarm-sync-status');
            if (syncStatus) {
                syncStatus.textContent = 'SYNCED';
                syncStatus.classList.add('text-green-500');
            }
        } else if (response.status === 403) {
            console.warn('[SWARM] 403: HMAC secret missing or wrong (see sentinel-hmac-secret meta).');
        }
    } catch (e) {
        console.warn("[SWARM] Backend sync failed. Check if server is running at " + resolveApiRoot());
    }
}

function updateSwarmHUD(nodes, latency, clusters) {
    const nodesEl = document.getElementById('swarm-active-nodes');
    const latencyEl = document.getElementById('swarm-latency');
    const clustersEl = document.getElementById('swarm-clusters');
    const syncStatus = document.getElementById('swarm-sync-status');

    if (nodesEl) nodesEl.textContent = nodes.toLocaleString();
    if (latencyEl) latencyEl.textContent = `${latency}ms`;
    if (clustersEl) clustersEl.textContent = clusters;
}

function findNearestNala(lat, lng) {
    const keys = Object.keys(nalaMesh);
    return keys[Math.floor(Math.random() * keys.length)];
}

function triggerNalaAlert(id, engine, map) {
    if (engine === 'leaflet') {
        const poly = nalaMesh[id];
        poly.setStyle({ color: NALA_CONFIG.alertColor, weight: NALA_CONFIG.alertWeight, opacity: 1.0 });
        poly.getElement().classList.add('pulse-alert');
        setTimeout(() => {
            poly.setStyle({ color: NALA_CONFIG.color, weight: NALA_CONFIG.weight, opacity: 0.4 });
            poly.getElement().classList.remove('pulse-alert');
        }, 5000);
    }
}
