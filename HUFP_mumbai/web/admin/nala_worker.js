/**
 * SENTINEL V7: SUBTERRANEAN SWARM INTELLIGENCE WORKER (nala_worker.js)
 * Processes 100,000+ IoT nodes in an isolated thread.
 */

const NODE_COUNT = 100000;
const MUMBAI_BOUNDS = { minLat: 18.85, maxLat: 19.35, minLng: 72.75, maxLng: 73.10 };
const CLUSTER_RADIUS_KM = 0.5;
const MIN_NODES_FOR_CHOKE = 15;

let nodes = [];

// --- Initialization ---
function initSwarm() {
    console.log(`[SWARM] Initializing ${NODE_COUNT} nodes...`);
    for (let i = 0; i < NODE_COUNT; i++) {
        nodes.push({
            id: i,
            lat: MUMBAI_BOUNDS.minLat + Math.random() * (MUMBAI_BOUNDS.maxLat - MUMBAI_BOUNDS.minLat),
            lng: MUMBAI_BOUNDS.minLng + Math.random() * (MUMBAI_BOUNDS.maxLng - MUMBAI_BOUNDS.minLng),
            level: Math.random() * 100,
            flow: Math.random() * 2
        });
    }
    console.log("[SWARM] Swarm ready.");
}

// --- Compute Loop ---
function processSwarm() {
    const startTime = performance.now();
    
    // 1. Simulate Fluctuations (Fast bitwise math equivalent)
    for (let i = 0; i < NODE_COUNT; i++) {
        nodes[i].level = Math.min(100, Math.max(0, nodes[i].level + (Math.random() * 10 - 5)));
        nodes[i].flow = Math.min(5, Math.max(0, nodes[i].flow + (Math.random() * 0.4 - 0.2)));
    }

    // 2. Anomaly Detection (Spatial Clustering)
    // To make it efficient for 100k nodes, we use a grid-based approach
    const gridSize = 0.005; // ~500m
    const grid = {};

    const chokePoints = [];
    
    for (let i = 0; i < NODE_COUNT; i++) {
        const node = nodes[i];
        if (node.level > 80 && node.flow < 0.5) {
            const gridX = Math.floor(node.lat / gridSize);
            const gridY = Math.floor(node.lng / gridSize);
            const key = `${gridX},${gridY}`;
            
            if (!grid[key]) grid[key] = [];
            grid[key].push(node);
        }
    }

    for (const key in grid) {
        if (grid[key].length >= MIN_NODES_FOR_CHOKE) {
            // Found a cluster
            const cluster = grid[key];
            const avgLat = cluster.reduce((sum, n) => sum + n.lat, 0) / cluster.length;
            const avgLng = cluster.reduce((sum, n) => sum + n.lng, 0) / cluster.length;
            
            chokePoints.push({
                lat: avgLat,
                lng: avgLng,
                severity: cluster.length,
                type: 'CHOKE_POINT'
            });
        }
    }

    const endTime = performance.now();
    const latency = Math.round(endTime - startTime);

    // 3. Post Results
    postMessage({
        totalNodes: NODE_COUNT,
        latency: latency,
        chokeClusters: chokePoints,
        biLstmPacket: {
            timestamp: Date.now(),
            active_nodes: NODE_COUNT,
            swarm_metrics: {
                active_clusters: chokePoints.length,
                high_risk_nodes: Object.values(grid).flat().length,
                system_load: 0.82
            }
        }
    });
}

// Start processing
initSwarm();
setInterval(processSwarm, 10000); // 10s loop

// --- Simulation Message Handler (Single Source of Truth Physics) ---
self.onmessage = async function(e) {
    if (e.data && e.data.type === 'SIMULATION_REQUEST') {
        const { mangrove_density, tide_height, rainfall_rate, api_base } = e.data;
        try {
            const response = await fetch(`${api_base}/api/v1/simulation/wave-attenuation`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    mangrove_density,
                    tide_height,
                    rainfall_rate
                })
            });
            if (response.ok) {
                const results = await response.json();
                postMessage({
                    type: 'SIMULATION_RESULT',
                    results
                });
            } else {
                console.error("[SWARM] Simulation endpoint returned error status:", response.status);
            }
        } catch (err) {
            console.error("[SWARM] Simulation fetch failed", err);
        }
    }
};
