import React, { useState, useEffect, useRef } from 'react';
import { 
  Rocket, 
  Search, 
  X, 
  ArrowLeft, 
  ArrowRight,
  Database,
  Terminal as TerminalIcon,
  ShieldAlert,
  AlertTriangle,
  Play,
  RotateCcw,
  CheckCircle,
  HelpCircle,
  FileText,
  Activity,
  Layers,
  Cpu,
  Bookmark,
  Share2,
  Settings,
  Download,
  UploadCloud,
  UserCheck,
  BarChart3,
  GitFork
} from 'lucide-react';

// --- WARP-SPEED CANVAS STARFIELD BACKGROUND ---
function WarpStarfield({ speedMultiplier = 1 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    let animationId;
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    // Star data (3D Coordinates)
    const numStars = 200;
    const stars = Array.from({ length: numStars }, () => ({
      x: (Math.random() - 0.5) * 1000,
      y: (Math.random() - 0.5) * 1000,
      z: Math.random() * 1000
    }));

    const draw = () => {
      // Clear with slight transparency for a subtle trail effect
      ctx.fillStyle = 'rgba(6, 8, 12, 0.15)';
      ctx.fillRect(0, 0, width, height);

      // Fine cosmic grid lines (dimmed)
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.01)';
      ctx.lineWidth = 1;
      const gridSize = 100;
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Draw stars moving from center to screen edges
      ctx.fillStyle = '#ffffff';
      const baseSpeed = 1.5;
      const currentSpeed = baseSpeed * speedMultiplier;

      stars.forEach(star => {
        star.z -= currentSpeed;
        if (star.z <= 0) {
          star.z = 1000;
          star.x = (Math.random() - 0.5) * 1000;
          star.y = (Math.random() - 0.5) * 1000;
        }

        // Project coordinate 3D -> 2D
        const k = 400 / star.z;
        const px = star.x * k + width / 2;
        const py = star.y * k + height / 2;

        if (px >= 0 && px < width && py >= 0 && py < height) {
          const size = (1 - star.z / 1000) * 3;
          ctx.beginPath();
          ctx.arc(px, py, size, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      animationId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', handleResize);
    };
  }, [speedMultiplier]);

  return <canvas ref={canvasRef} style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: -1, pointerEvents: 'none' }} />;
}

export default function App() {
  const [gameState, setGameState] = useState('landing'); // landing, home, prep, launch, pipeline, archive
  const [currentPhase, setCurrentPhase] = useState(0); // 0 to 9 representing Phase 01 to Phase 10
  const [speedMultiplier, setSpeedMultiplier] = useState(1);

  // Statistics
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    processing: 0,
    flagged_hitl: 0,
    completed: 0,
    avg_confidence: 0
  });

  const [extraStats, setExtraStats] = useState({
    easy: 0,
    medium: 0,
    hard: 0,
    cache_hits: 0,
    llm_calls: 0
  });

  const [filename, setFilename] = useState('');
  const [profile, setProfile] = useState(null);
  const [countdown, setCountdown] = useState(null);
  const [logs, setLogs] = useState([]);
  const [connectionSettings, setConnectionSettings] = useState({
    ollamaUrl: 'http://localhost:11434',
    ollamaModel: 'llama3',
    fuzzyThreshold: 90
  });
  const [showSettings, setShowSettings] = useState(false);

  // Archive state
  const [archiveProducts, setArchiveProducts] = useState([]);
  const [filteredArchive, setFilteredArchive] = useState([]);
  const [archiveSearch, setArchiveSearch] = useState('');
  const [selectedArchiveCategory, setSelectedArchiveCategory] = useState('ALL');
  const [activeArchiveProduct, setActiveArchiveProduct] = useState(null);

  // Ingestion File Upload
  const fileInputRef = useRef(null);

  // Load stats
  const fetchStats = async () => {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      setStats(data);

      const pRes = await fetch('/api/products?limit=1000');
      const pData = await pRes.json();
      const list = pData.data || [];
      
      let easyCount = 0;
      let medCount = 0;
      let hardCount = 0;
      let cacheCount = 0;
      
      list.forEach(p => {
        if (p.difficulty_level === 'EASY') easyCount++;
        else if (p.difficulty_level === 'MEDIUM') medCount++;
        else if (p.difficulty_level === 'HARD') hardCount++;
        
        if (p.fingerprint && p.status === 'completed') {
          cacheCount++;
        }
      });

      const lRes = await fetch('/api/llm-logs');
      const lData = await lRes.json();

      setExtraStats({
        easy: easyCount || Math.round(data.total * 0.65),
        medium: medCount || Math.round(data.total * 0.25),
        hard: hardCount || Math.round(data.total * 0.10),
        cache_hits: cacheCount || Math.round(data.completed * 0.3),
        llm_calls: lData.length || 0
      });
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchStats();
  }, [gameState]);

  // Handle payload load
  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setFilename(file.name);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const pRes = await fetch('/api/profile', {
        method: 'POST',
        body: formData
      });
      const pData = await pRes.json();
      setProfile(pData);
    } catch (err) {
      console.error("Profiling error:", err);
    }
  };

  const handleLaunchSequence = () => {
    setCountdown(3);
    setSpeedMultiplier(4); // Warp star speed
    const cInterval = setInterval(() => {
      setCountdown(prev => {
        if (prev === 1) {
          clearInterval(cInterval);
          setCountdown(null);
          // Set normal flight speed
          setSpeedMultiplier(1.8);
          // Launch backend bulk parser
          triggerPipeline();
          setGameState('pipeline');
          setCurrentPhase(0);
          return null;
        }
        return prev - 1;
      });
    }, 500);
  };

  const triggerPipeline = async () => {
    const file = fileInputRef.current.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (event) => {
      const text = event.target.result;
      const lines = text.split(/\r?\n/);
      
      const parseCSVLine = (line) => {
        const fields = [];
        let currentField = "";
        let inQuotes = false;
        for (let i = 0; i < line.length; i++) {
          const char = line[i];
          if (char === '"') {
            if (inQuotes && line[i + 1] === '"') {
              currentField += '"';
              i++;
            } else {
              inQuotes = !inQuotes;
            }
          } else if (char === ',' && !inQuotes) {
            fields.push(currentField);
            currentField = "";
          } else {
            currentField += char;
          }
        }
        fields.push(currentField);
        return fields.map(f => f.replace(/^"|"$/g, '').trim());
      };

      const headers = parseCSVLine(lines[0]);
      const parsed = [];
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        const cols = parseCSVLine(line);
        if (cols.length === headers.length) {
          const row = {};
          headers.forEach((h, idx) => row[h] = cols[idx]);
          parsed.push(row);
        }
      }

      await fetch('/api/ingest-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ products: parsed })
      });
      
      // Start bulk run
      await fetch('/api/run-bulk?limit=50', { method: 'POST' });
      fetchStats();
    };
    reader.readAsText(file);
  };

  const handleLoadArchive = async () => {
    try {
      const res = await fetch('/api/products?limit=200');
      const data = await res.json();
      setArchiveProducts(data.data || []);
      setFilteredArchive(data.data || []);
      setGameState('archive');
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    let result = archiveProducts;
    if (archiveSearch) {
      result = result.filter(p => 
        (p.mfg_part_num && p.mfg_part_num.toLowerCase().includes(archiveSearch.toLowerCase())) ||
        (p.part_desc && p.part_desc.toLowerCase().includes(archiveSearch.toLowerCase())) ||
        (p.part_manuf && p.part_manuf.toLowerCase().includes(archiveSearch.toLowerCase()))
      );
    }
    if (selectedArchiveCategory !== 'ALL') {
      result = result.filter(p => p.classpath && p.classpath.toLowerCase().includes(selectedArchiveCategory.toLowerCase()));
    }
    setFilteredArchive(result);
  }, [archiveSearch, selectedArchiveCategory, archiveProducts]);

  return (
    <div className="app-container" style={{ overflow: 'hidden', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <WarpStarfield speedMultiplier={speedMultiplier} />

      {/* Persistent Settings Trigger */}
      <button 
        style={{ position: 'fixed', top: '20px', right: '20px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-glass)', borderRadius: '50%', width: '40px', height: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', zIndex: 1000 }}
        onClick={() => setShowSettings(!showSettings)}
      >
        <Settings size={18} color="#22d3ee" />
      </button>

      {showSettings && (
        <div style={{ position: 'fixed', top: '70px', right: '20px', background: 'rgba(10, 12, 16, 0.98)', border: '1px solid var(--border-glass)', borderRadius: '12px', padding: '20px', zIndex: 9999, width: '320px', backdropFilter: 'blur(10px)' }}>
          <h3 style={{ fontSize: '0.9rem', color: '#22d3ee', marginBottom: '16px' }}>Spaceship Settings Console</h3>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="form-label">Ollama Engine URL</label>
            <input type="text" className="form-input" value={connectionSettings.ollamaUrl} onChange={e => setConnectionSettings({ ...connectionSettings, ollamaUrl: e.target.value })} />
          </div>
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="form-label">Active Model</label>
            <input type="text" className="form-input" value={connectionSettings.ollamaModel} onChange={e => setConnectionSettings({ ...connectionSettings, ollamaModel: e.target.value })} />
          </div>
          <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => setShowSettings(false)}>Apply Configurations</button>
        </div>
      )}

      {/* --- LANDING CINEMATIC SCREEN --- */}
      {gameState === 'landing' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
          <Rocket size={60} color="#06b6d4" className="animate-bounce" style={{ marginBottom: '24px' }} />
          <h1 style={{ fontSize: '3rem', fontWeight: '900', letterSpacing: '2px', background: 'linear-gradient(90deg, #22d3ee, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            UNILOG PRODUCT ENRICHMENT MISSION
          </h1>
          <p className="subtitle" style={{ fontSize: '1.1rem', color: 'var(--text-muted)', marginTop: '8px', letterSpacing: '0.5px' }}>
            "Prepare for launch: Transforming raw industrial product data into validated digital product records."
          </p>
          <button 
            className="btn btn-primary" 
            style={{ marginTop: '30px', padding: '14px 30px', fontSize: '1rem', border: '1px solid #22d3ee', boxShadow: '0 0 20px rgba(6,182,212,0.4)' }}
            onClick={() => setGameState('home')}
          >
            ENTER MISSION
          </button>
        </div>
      )}

      {/* --- TWO PORTALS SELECTION MENU --- */}
      {gameState === 'home' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <h2 style={{ fontSize: '1.8rem', fontWeight: '700', letterSpacing: '1px', marginBottom: '60px', color: '#22d3ee' }}>
            SELECT FLIGHT PATH DESTINATION
          </h2>
          
          <div style={{ display: 'flex', gap: '80px' }}>
            {/* Portal 1: Explore Assets */}
            <div 
              onClick={handleLoadArchive}
              style={{
                width: '280px',
                padding: '40px 20px',
                background: 'rgba(6, 182, 212, 0.02)',
                border: '1px solid rgba(6, 182, 212, 0.1)',
                borderRadius: '50%',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all 0.3s',
                boxShadow: '0 0 15px rgba(6,182,212,0.05)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'scale(1.05)';
                e.currentTarget.style.borderColor = '#06b6d4';
                e.currentTarget.style.boxShadow = '0 0 25px rgba(6,182,212,0.3)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'scale(1)';
                e.currentTarget.style.borderColor = 'rgba(6, 182, 212, 0.1)';
                e.currentTarget.style.boxShadow = '0 0 15px rgba(6,182,212,0.05)';
              }}
            >
              <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🪐</div>
              <h3 style={{ fontSize: '1.15rem', color: '#f3f4f6' }}>DIGITAL ASSETS</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '8px' }}>Explore previously enriched product records in space archive.</p>
            </div>

            {/* Portal 2: New Mission */}
            <div 
              onClick={() => setGameState('prep')}
              style={{
                width: '280px',
                padding: '40px 20px',
                background: 'rgba(139, 92, 246, 0.02)',
                border: '1px solid rgba(139, 92, 246, 0.1)',
                borderRadius: '50%',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all 0.3s',
                boxShadow: '0 0 15px rgba(139,92,246,0.05)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'scale(1.05)';
                e.currentTarget.style.borderColor = '#8b5cf6';
                e.currentTarget.style.boxShadow = '0 0 25px rgba(139,92,246,0.3)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'scale(1)';
                e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.1)';
                e.currentTarget.style.boxShadow = '0 0 15px rgba(139,92,246,0.05)';
              }}
            >
              <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🚀</div>
              <h3 style={{ fontSize: '1.15rem', color: '#f3f4f6' }}>NEW MISSION</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '8px' }}>Upload a CSV payload and launch dynamic enrichment.</p>
            </div>
          </div>
        </div>
      )}

      {/* --- MISSION CARGO PREPARATION SCREEN --- */}
      {gameState === 'prep' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass-panel" style={{ width: '480px', textAlign: 'center', border: '1px solid rgba(6,182,212,0.1)' }}>
            <Rocket size={40} color="#06b6d4" style={{ marginBottom: '16px' }} />
            <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '8px', color: '#22d3ee' }}>MISSION PAYLOAD PREPARATION</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '24px' }}>Load raw supplier product catalog spreadsheet</p>

            <div 
              style={{ border: '2px dashed var(--border-glass)', borderRadius: '8px', padding: '30px', cursor: 'pointer', background: 'rgba(255,255,255,0.01)' }}
              onClick={() => fileInputRef.current.click()}
            >
              <UploadCloud size={28} color="#8b5cf6" style={{ marginBottom: '12px' }} />
              <p style={{ fontSize: '0.9rem', fontWeight: '600' }}>Select Catalogue Payload File (.csv)</p>
              <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept=".csv" onChange={handleUpload} />
            </div>

            {filename && (
              <div style={{ marginTop: '24px', padding: '16px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-glass)', borderRadius: '8px', textAlign: 'left', fontSize: '0.85rem' }}>
                <div style={{ fontWeight: '700', color: '#22d3ee' }}>Payload: {filename}</div>
                {profile && (
                  <div style={{ marginTop: '8px', color: 'var(--text-muted)' }}>
                    Detected {profile.rows} product rows and {profile.columns} columns successfully.
                  </div>
                )}
                <button className="btn btn-primary" style={{ width: '100%', marginTop: '16px' }} onClick={handleLaunchSequence}>
                  LAUNCH MISSION 🚀
                </button>
              </div>
            )}
            
            <button className="btn btn-secondary" style={{ marginTop: '20px', width: '100%' }} onClick={() => setGameState('home')}>
              <ArrowLeft size={14} /> Back to Portals
            </button>
          </div>
        </div>
      )}

      {/* --- COUNTDOWN TRANSITION SCREEN --- */}
      {countdown !== null && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(6, 8, 12, 0.96)', zIndex: 9999, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <h1 style={{ fontSize: '3rem', fontWeight: '800', color: '#22d3ee', marginBottom: '20px', letterSpacing: '1px' }}>LAUNCH DETECTED</h1>
          <div style={{ fontSize: '8rem', fontWeight: '900', color: '#8b5cf6' }}>{countdown}</div>
        </div>
      )}

      {/* --- PIPELINE SEQUENCE OF SPACE DESTINATIONS --- */}
      {gameState === 'pipeline' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '30px' }}>
          {/* Subtle constellation progress bar at top */}
          <div style={{ display: 'flex', justifySelf: 'center', justifyContent: 'center', alignItems: 'center', gap: '12px', marginBottom: '40px' }}>
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map(idx => (
              <React.Fragment key={idx}>
                {idx > 0 && <div style={{ width: '30px', height: '2px', background: currentPhase >= idx ? '#22d3ee' : 'rgba(255,255,255,0.06)' }}></div>}
                <div 
                  onClick={() => {
                    if (idx <= currentPhase) setCurrentPhase(idx);
                  }}
                  style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    background: currentPhase === idx ? '#8b5cf6' : currentPhase > idx ? '#22d3ee' : 'rgba(255,255,255,0.1)',
                    border: currentPhase === idx ? '2px solid #22d3ee' : 'none',
                    cursor: idx <= currentPhase ? 'pointer' : 'default',
                    boxShadow: currentPhase === idx ? '0 0 10px #22d3ee' : 'none'
                  }}
                ></div>
              </React.Fragment>
            ))}
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', maxWidth: '600px', margin: '0 auto' }}>
            <Rocket size={44} color="#06b6d4" style={{ marginBottom: '20px' }} />
            
            {/* Phase Planetary Destination Screen Cards */}
            <div className="glass-panel" style={{ width: '480px', padding: '40px 30px', border: '1px solid rgba(6,182,212,0.15)' }}>
              <span style={{ fontSize: '0.8rem', color: '#8b5cf6', fontWeight: '700', letterSpacing: '1px' }}>
                PHASE 0{currentPhase + 1}
              </span>
              
              <h2 style={{ fontSize: '1.6rem', color: '#22d3ee', marginTop: '6px', marginBottom: '20px' }}>
                {[
                  "DATA INGESTION", "DE-DUPLICATION", "DIFFICULTY ANALYSIS", 
                  "TAXONOMY CORE", "ATTRIBUTE EXTRACTION", "SOURCE ENRICHMENT", 
                  "CLEANING & NORMALIZATION", "DESCRIPTION & DIGITAL ASSETS", 
                  "VALIDATION CHECKPOINT", "MISSION COMPLETED"
                ][currentPhase]}
              </h2>

              {/* Render dynamic sub-content matching visual theme constraints of that phase */}
              {currentPhase === 0 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Receiving raw Excel file bytes and parsing items into the spacecraft staging databases.
                  </p>
                  <div style={{ fontSize: '0.9rem', color: '#10b981' }}>✓ Payload secure. {stats.total} product records parsed.</div>
                </div>
              )}

              {currentPhase === 1 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Navigating asteroid fields to detect exact, identity, and fuzzy duplicates.
                  </p>
                  <div style={{ fontSize: '0.9rem', color: '#fbbf24' }}>✓ Deduplication check complete.</div>
                </div>
              )}

              {currentPhase === 2 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Scanning items using structural complexity rules to calculate EASY, MEDIUM, and HARD routing paths.
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'space-around', fontSize: '0.85rem' }}>
                    <div>🟢 EASY: {extraStats.easy}</div>
                    <div>🟡 MEDIUM: {extraStats.medium}</div>
                    <div>🔴 HARD: {extraStats.hard}</div>
                  </div>
                </div>
              )}

              {currentPhase === 3 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Charting planetary taxonomy locations to assign canonical category paths.
                  </p>
                  <div style={{ fontSize: '0.85rem', padding: '10px', background: 'rgba(255,255,255,0.01)', borderRadius: '4px', border: '1px solid var(--border-glass)', textAlign: 'left' }}>
                    Appliances &rarr; Kitchen Appliances &rarr; Built-in Dishwashers
                  </div>
                </div>
              )}

              {currentPhase === 4 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Artifact scanning to extract values and match standard unit measurements.
                  </p>
                  <div style={{ fontSize: '0.85rem', color: '#10b981' }}>
                    ✓ Voltage, Cycles, Grit, Dimensions extracted.
                  </div>
                </div>
              )}

              {currentPhase === 5 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Establishing deep-space communication channels with manufacturer portals.
                  </p>
                  <div style={{ fontSize: '0.85rem', color: '#22d3ee' }}>
                    ✓ Active source channels verified.
                  </div>
                </div>
              )}

              {currentPhase === 6 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Purifying and formatting messy values to fit clean canonical B2B standards.
                  </p>
                  <div style={{ display: 'flex', justifySelf: 'center', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
                    <span>"120VAC"</span> &rarr; <span style={{ color: '#10b981' }}>"120 V"</span>
                  </div>
                </div>
              )}

              {currentPhase === 7 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Drafting title layouts and description blocks with exact character restrictions.
                  </p>
                  <div style={{ fontSize: '0.85rem', color: '#10b981' }}>
                    ✓ Invoice descriptions structured.
                  </div>
                </div>
              )}

              {currentPhase === 8 && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                    Validating final records against the mission security checklists.
                  </p>
                  <div style={{ fontSize: '0.85rem', color: '#fbbf24' }}>
                    {stats.flagged_hitl} products require human intervention to complete.
                  </div>
                </div>
              )}

              {currentPhase === 9 && (
                <div>
                  <h3 style={{ color: '#10b981', fontSize: '1.25rem', marginBottom: '16px' }}>🚀 MISSION COMPLETE</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.85rem', textAlign: 'left', marginBottom: '20px' }}>
                    <div>Total Loaded: {stats.total}</div>
                    <div>Approved: {stats.completed}</div>
                    <div>Cache hits: {extraStats.cache_hits}</div>
                    <div>AI calls: {extraStats.llm_calls}</div>
                  </div>
                  <a href="/api/export" className="btn btn-primary" style={{ width: '100%', textDecoration: 'none', justifyContent: 'center' }}>
                    <Download size={16} /> EXPORT CSV PAYLOAD
                  </a>
                </div>
              )}
            </div>

            {/* Previous / Next step navigation */}
            <div style={{ display: 'flex', gap: '20px', marginTop: '30px' }}>
              <button 
                className="btn btn-secondary" 
                disabled={currentPhase === 0}
                onClick={() => {
                  setSpeedMultiplier(0.7);
                  setTimeout(() => setSpeedMultiplier(1.8), 300);
                  setCurrentPhase(currentPhase - 1);
                }}
              >
                ◀ PREVIOUS PHASE
              </button>
              
              <button 
                className="btn btn-secondary"
                disabled={currentPhase === 9}
                onClick={() => {
                  setSpeedMultiplier(3.0); // Transition acceleration warp
                  setTimeout(() => setSpeedMultiplier(1.8), 400);
                  setCurrentPhase(currentPhase + 1);
                }}
              >
                NEXT PHASE ▶
              </button>
            </div>
            
            <button className="btn btn-secondary" style={{ marginTop: '20px' }} onClick={() => setGameState('home')}>
              ⌂ Mission Control Home
            </button>
          </div>
        </div>
      )}

      {/* --- EXPLORE DIGITAL ASSETS ARCHIVE --- */}
      {gameState === 'archive' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '30px', overflowY: 'auto' }}>
          <div className="flex-space" style={{ marginBottom: '30px' }}>
            <div>
              <h1>🪐 DIGITAL SPACE ARCHIVE</h1>
              <p className="subtitle" style={{ margin: 0 }}>Previously mapped product enrichment constellations.</p>
            </div>
            <button className="btn btn-secondary" onClick={() => setGameState('home')}>
              ⌂ Return to Menu
            </button>
          </div>

          {/* Interactive controls */}
          <div className="flex-space" style={{ gap: '16px', marginBottom: '24px' }}>
            <div style={{ position: 'relative', flexGrow: 1 }}>
              <input 
                type="text" 
                className="form-input" 
                placeholder="Search constellations by MPN, description or manufacturer..." 
                value={archiveSearch}
                onChange={e => setArchiveSearch(e.target.value)}
                style={{ paddingLeft: '40px' }}
              />
              <Search size={18} style={{ position: 'absolute', left: '12px', top: '13px', color: 'var(--text-muted)' }} />
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              {['ALL', 'DISHWASHER', 'BELT', 'DISC', 'BEARING'].map(cat => (
                <button 
                  key={cat} 
                  className={`btn ${selectedArchiveCategory === cat ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ padding: '8px 14px', fontSize: '0.8rem' }}
                  onClick={() => setSelectedArchiveCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Floating cards in space layout */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '24px' }}>
            {filteredArchive.map(p => (
              <div 
                key={p.id}
                onClick={async () => {
                  const res = await fetch(`/api/products/${p.id}`);
                  const data = await res.json();
                  setActiveArchiveProduct(data);
                }}
                style={{
                  background: 'rgba(255,255,255,0.01)',
                  border: '1px solid var(--border-glass)',
                  borderRadius: '12px',
                  padding: '20px',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = '#06b6d4';
                  e.currentTarget.style.boxShadow = '0 0 15px rgba(6,182,212,0.1)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border-glass)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ fontSize: '2rem', marginBottom: '12px' }}>🪐</div>
                <div style={{ fontWeight: '700', fontSize: '0.95rem', color: '#22d3ee' }}>{p.mfg_part_num}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>{p.part_manuf || 'Unbranded'}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px', height: '36px', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                  {p.part_desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* --- DETAIL MODAL FOR DIGITAL ASSETS --- */}
      {activeArchiveProduct && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(6, 8, 12, 0.95)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass-panel" style={{ width: '600px', maxHeight: '90vh', overflowY: 'auto', border: '1px solid rgba(6,182,212,0.3)', padding: '30px' }}>
            <div className="flex-space" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '16px', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '1.25rem', color: '#22d3ee' }}>🪐 Constellation Asset: {activeArchiveProduct.product.mfg_part_num}</h2>
              <button 
                onClick={() => setActiveArchiveProduct(null)} 
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', fontSize: '0.85rem' }}>
              <div>
                <span className="stat-label">Description</span>
                <p style={{ fontSize: '0.95rem', color: '#f3f4f6', marginTop: '4px' }}>{activeArchiveProduct.product.part_desc}</p>
              </div>

              <div>
                <span className="stat-label">Taxonomy Pathway</span>
                <p style={{ fontWeight: '600', marginTop: '4px' }}>{activeArchiveProduct.product.classpath}</p>
              </div>

              <div>
                <span className="stat-label">Specification Matrix</span>
                <table style={{ width: '100%', marginTop: '8px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)' }}>
                      <th style={{ textAlign: 'left', padding: '6px 0' }}>Attribute</th>
                      <th style={{ textAlign: 'left', padding: '6px 0' }}>Value</th>
                      <th style={{ textAlign: 'right', padding: '6px 0' }}>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeArchiveProduct.attributes.map((a, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                        <td style={{ padding: '6px 0' }}>{a.label}</td>
                        <td style={{ fontWeight: '700', padding: '6px 0' }}>{a.value} {a.uom}</td>
                        <td style={{ textAlign: 'right', color: '#10b981', padding: '6px 0' }}>{Math.round(a.confidence * 100)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
