importScripts("https://cdn.jsdelivr.net/npm/@turf/turf@6/turf.min.js");

self.onmessage = function(e) {
    const { start, end, mangrovesGeoJSON } = e.data;
    
    if (!start || !end) {
        postMessage({ error: "Missing start or end coordinates." });
        return;
    }
    
    // Turf coordinates are in [longitude, latitude]
    const directLine = turf.lineString([start, end]);
    let safeRoute = [start, end];
    let intersected = false;
    let intersectedPolygonName = "";
    
    if (mangrovesGeoJSON && mangrovesGeoJSON.features) {
        for (const feature of mangrovesGeoJSON.features) {
            // Check if mangrove area is degraded or felled (density < 60%)
            const density = feature.properties.density || 100;
            if (density < 60) {
                const intersection = turf.lineIntersect(directLine, feature);
                
                if (intersection.features.length > 0) {
                    intersected = true;
                    intersectedPolygonName = feature.properties.name;
                    
                    // Detour via bounding box corners to avoid the degraded zone
                    const bbox = turf.bbox(feature); // [minX, minY, maxX, maxY]
                    const corners = [
                        [bbox[0], bbox[1]],
                        [bbox[2], bbox[1]],
                        [bbox[2], bbox[3]],
                        [bbox[0], bbox[3]]
                    ];
                    
                    // Choose the corner that minimizes the bypass detour distance (start -> corner -> end)
                    let minDistance = Infinity;
                    let bestCorner = corners[0];
                    
                    const startPt = turf.point(start);
                    const endPt = turf.point(end);
                    
                    for (const corner of corners) {
                        const cornerPt = turf.point(corner);
                        const d = turf.distance(startPt, cornerPt) + turf.distance(cornerPt, endPt);
                        if (d < minDistance) {
                            minDistance = d;
                            bestCorner = corner;
                        }
                    }
                    
                    safeRoute = [start, bestCorner, end];
                    break;
                }
            }
        }
    }
    
    postMessage({
        safeRoute: safeRoute,
        intersected: intersected,
        intersectedPolygonName: intersectedPolygonName
    });
};
