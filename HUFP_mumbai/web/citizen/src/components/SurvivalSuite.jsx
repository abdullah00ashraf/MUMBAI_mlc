import React, { useState, useEffect, useRef } from 'react';
import './SurvivalSuite.css'; // Assuming styling is here

const SurvivalSuite = () => {
  const [lockProbability, setLockProbability] = useState(0.0);
  const [telemetry, setTelemetry] = useState({ rain_mm: 0, tide_m: 0 });
  const [isConnected, setIsConnected] = useState(false);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const backoffRef = useRef(1000); // Start with 1 second backoff

  const connectWebSocket = () => {
    // Clear any existing timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    const wsUrl = "ws://localhost:8000/ws/telemetry";
    console.log(`[WebSocket] Attempting to connect to ${wsUrl}`);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("[WebSocket] Connection established.");
      setIsConnected(true);
      backoffRef.current = 1000; // Reset backoff on successful connection
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.hydraulic_lock_probability !== undefined) {
          setLockProbability(data.hydraulic_lock_probability);
        }
        if (data.rain_mm !== undefined || data.tide_m !== undefined) {
          setTelemetry(prev => ({
            rain_mm: data.rain_mm !== undefined ? data.rain_mm : prev.rain_mm,
            tide_m: data.tide_m !== undefined ? data.tide_m : prev.tide_m
          }));
        }
      } catch (err) {
        console.error("[WebSocket] Error parsing JSON:", err);
      }
    };

    ws.onclose = () => {
      console.warn("[WebSocket] Connection closed.");
      setIsConnected(false);
      scheduleReconnect();
    };

    ws.onerror = (error) => {
      console.error("[WebSocket] Error encountered:", error);
      ws.close(); // Will trigger onclose and then reconnect
    };

    wsRef.current = ws;
  };

  const scheduleReconnect = () => {
    // Exponential backoff up to 30 seconds max
    const maxBackoff = 30000;
    const currentBackoff = backoffRef.current;
    
    console.log(`[WebSocket] Reconnecting in ${currentBackoff / 1000} seconds...`);
    reconnectTimeoutRef.current = setTimeout(() => {
      connectWebSocket();
    }, currentBackoff);

    backoffRef.current = Math.min(currentBackoff * 2, maxBackoff);
  };

  useEffect(() => {
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        console.log("[WebSocket] Unmounting Component. Closing connection.");
        wsRef.current.close();
      }
    };
  }, []);

  // Determine emergency state
  const isEmergency = lockProbability > 0.85;
  const cubeClass = isEmergency ? "survival-cube cube-emergency-red" : "survival-cube cube-nominal";

  return (
    <div className="survival-suite-container">
      <div className="glassmorphic-panel">
        <header className="suite-header">
          <h2>SENTINEL V7</h2>
          <span className={`status-indicator ${isConnected ? 'online' : 'offline'}`}>
            {isConnected ? 'SECURE LINK ACTIVE' : 'LINK OFFLINE'}
          </span>
        </header>
        
        <div className="cube-container">
          <div className={cubeClass}>
             {/* 3D faces would go here */}
             <div className="cube-face front">
               <h3>HUD</h3>
               <p className={isEmergency ? "text-critical" : "text-safe"}>
                 LOCK PROB: {(lockProbability * 100).toFixed(1)}%
               </p>
             </div>
          </div>
        </div>

        <div className="telemetry-readout">
          <div className="metric">
            <label>PRECIPITATION</label>
            <span>{telemetry.rain_mm.toFixed(2)} mm/hr</span>
          </div>
          <div className="metric">
            <label>TIDE LEVEL</label>
            <span>{telemetry.tide_m.toFixed(2)} m</span>
          </div>
        </div>
        
        {isEmergency && (
          <div className="emergency-warning">
            WARNING: HYDRAULIC LOCK DETECTED. SEEK HIGH GROUND.
          </div>
        )}
      </div>
    </div>
  );
};

export default SurvivalSuite;
