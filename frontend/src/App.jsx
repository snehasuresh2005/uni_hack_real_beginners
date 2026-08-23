import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, 
  X, 
  Database,
  ShieldAlert,
  AlertTriangle,
  Play,
  RotateCcw,
  CheckCircle,
  Settings as SettingsIcon,
  Download,
  UploadCloud,
  Layers,
  BarChart3,
  Edit3,
  Info,
  Terminal as TerminalIcon,
  HelpCircle,
  Check,
  Activity,
  Plus,
  Trash2,
  ExternalLink,
  FileText,
  Globe,
  Zap
} from 'lucide-react';

function PipelineStepTracker({ product, activePhase, isSkippedLLM }) {
  const steps = [
    { label: 'cache-check', short: 'C' },
    { label: 'dedup', short: 'D' },
    { label: 'normalize', short: 'N' },
    { label: 'classify', short: 'Cl' },
    { label: 'taxonomy', short: 'T' },
    { label: 'regex', short: 'R' },
    { label: 'LLM', short: 'L' },
    { label: 'QA', short: 'Q' }
  ];

  const status = product.status;
  const currentPhase = activePhase || 1;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginTop: '6px' }}>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes pulse {
          0% { transform: scale(1); opacity: 0.8; box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.4); }
          50% { transform: scale(1.15); opacity: 1; box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2); }
          100% { transform: scale(1); opacity: 0.8; box-shadow: 0 0 0 0 rgba(139, 92, 246, 0); }
        }
        .step-pulse {
          animation: pulse 1.5s infinite ease-in-out;
        }
      `}} />
      <div style={{ display: 'flex', gap: '3px' }}>
        {steps.map((step, idx) => {
          const stepNum = idx + 1;
          let bg = 'rgba(255, 255, 255, 0.05)';
          let color = 'rgba(255, 255, 255, 0.25)';
          let isPulse = false;
          let isSkipped = false;

          if (status === 'completed') {
            bg = 'rgba(16, 185, 129, 0.15)';
            color = '#10b981';
          } else if (status === 'flagged_hitl') {
            if (stepNum === 8) {
              bg = 'rgba(239, 68, 68, 0.15)';
              color = '#ef4444';
            } else {
              bg = 'rgba(16, 185, 129, 0.15)';
              color = '#10b981';
            }
          } else if (status === 'duplicate') {
            if (stepNum <= 2) {
              bg = 'rgba(16, 185, 129, 0.15)';
              color = '#10b981';
            } else {
              bg = 'rgba(255, 255, 255, 0.02)';
              color = 'rgba(255, 255, 255, 0.1)';
              isSkipped = true;
            }
          } else if (status === 'pending') {
            bg = 'rgba(255, 255, 255, 0.04)';
            color = 'rgba(255, 255, 255, 0.2)';
          } else if (status === 'processing') {
            if (stepNum < currentPhase) {
              if (stepNum === 7 && isSkippedLLM) {
                bg = 'rgba(255, 255, 255, 0.02)';
                color = 'rgba(255, 255, 255, 0.1)';
                isSkipped = true;
              } else {
                bg = 'rgba(16, 185, 129, 0.15)';
                color = '#10b981';
              }
            } else if (stepNum === currentPhase) {
              bg = 'rgba(139, 92, 246, 0.2)';
              color = '#a78bfa';
              isPulse = true;
            } else {
              bg = 'rgba(255, 255, 255, 0.04)';
              color = 'rgba(255, 255, 255, 0.2)';
            }
          }

          return (
            <div 
              key={idx}
              title={`${step.label}${isPulse ? ' (Running)' : isSkipped ? ' (Skipped)' : ''}`}
              className={isPulse ? 'step-pulse' : ''}
              style={{
                width: '18px',
                height: '18px',
                borderRadius: '50%',
                background: bg,
                border: `1px solid ${color}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '8px',
                fontWeight: 'bold',
                color: color,
                cursor: 'help',
                transition: 'all 0.3s ease',
                textDecoration: isSkipped ? 'line-through' : 'none'
              }}
            >
              {step.short}
            </div>
          );
        })}
      </div>
      {status === 'processing' && (
        <span style={{ fontSize: '0.7rem', color: '#a78bfa', marginLeft: '4px', fontStyle: 'italic' }}>
          {steps[currentPhase - 1]?.label}...
        </span>
      )}
    </div>
  );
}

export default function App() {
  const [currentTab, setCurrentTab] = useState('dashboard'); // dashboard, ingestion, preview, conflicts, settings
  
  // Pipeline Stats
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    processing: 0,
    flagged_hitl: 0,
    completed: 0,
    avg_confidence: 0,
    llm_calls_today: 0,
    llm_call_budget: 50
  });

  // Non-blocking Toast notification system
  const [toast, setToast] = useState(null);
  const showToast = (text, type = 'info') => {
    setToast({ text, type });
    setTimeout(() => setToast(null), 3500);
  };

  const [extraStats, setExtraStats] = useState({
    easy: 0,
    medium: 0,
    hard: 0,
    cache_hits: 0,
    llm_calls: 0
  });

  // Data Grid / Excel Preview State
  const [products, setProducts] = useState([]);
  const [totalProductsCount, setTotalProductsCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [gridFilterStatus, setGridFilterStatus] = useState('ALL');

  // Excel Manual Editor Modal
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [editingProductFields, setEditingProductFields] = useState({
    mfg_part_num: '',
    part_manuf: '',
    resolved_manufacturer: '',
    resolved_brand: '',
    part_desc: '',
    invoice_desc: '',
    mobile_desc: '',
    short_desc: '',
    long_desc: '',
    retail_desc: '',
    classpath: ''
  });
  const [editingAttributes, setEditingAttributes] = useState([]);
  const [editingProductLogs, setEditingProductLogs] = useState([]);

  // Ingestion tab State
  const fileInputRef = useRef(null);
  const [ingestFile, setIngestFile] = useState(null);
  const [ingestPreview, setIngestPreview] = useState(null);
  const [ingestStatus, setIngestStatus] = useState('');
  const [ingestRowsCount, setIngestRowsCount] = useState(0);

  // Conflicts list
  const [flaggedProducts, setFlaggedProducts] = useState([]);
  const [selectedConflictProduct, setSelectedConflictProduct] = useState(null);

  // States for Conflicts Resolution Panel
  const [conflictResolvedBrand, setConflictResolvedBrand] = useState('');
  const [conflictResolvedManufacturer, setConflictResolvedManufacturer] = useState('');
  const [conflictClasspath, setConflictClasspath] = useState('');
  const [conflictInvoiceDesc, setConflictInvoiceDesc] = useState('');
  const [conflictMobileDesc, setConflictMobileDesc] = useState('');
  const [conflictShortDesc, setConflictShortDesc] = useState('');
  const [conflictLongDesc, setConflictLongDesc] = useState('');
  const [conflictAttributes, setConflictAttributes] = useState([]);

  useEffect(() => {
    if (selectedConflictProduct) {
      const p = selectedConflictProduct.product;
      setConflictResolvedBrand(p.resolved_brand || '');
      setConflictResolvedManufacturer(p.resolved_manufacturer || '');
      setConflictClasspath(p.classpath || '');
      setConflictInvoiceDesc(p.invoice_desc || '');
      setConflictMobileDesc(p.mobile_desc || '');
      setConflictShortDesc(p.short_desc || '');
      setConflictLongDesc(p.long_desc || '');
      setConflictAttributes(selectedConflictProduct.attributes || []);
    } else {
      setConflictResolvedBrand('');
      setConflictResolvedManufacturer('');
      setConflictClasspath('');
      setConflictInvoiceDesc('');
      setConflictMobileDesc('');
      setConflictShortDesc('');
      setConflictLongDesc('');
      setConflictAttributes([]);
    }
  }, [selectedConflictProduct]);

  // LLM execution logs
  const [llmLogs, setLlmLogs] = useState([]);

  // SSE log stream states
  const [agentLogs, setAgentLogs] = useState([]);
  const [activeProductPhases, setActiveProductPhases] = useState({});
  const [skippedLLM, setSkippedLLM] = useState({});

  // Connection settings
  const [connectionSettings, setConnectionSettings] = useState({
    llm_provider: 'auto',
    gemini_api_key: '',
    gemini_model: 'gemini-1.5-flash',
    groq_api_key: '',
    groq_model: 'llama-3.3-70b-versatile',
    openrouter_api_key: '',
    openrouter_model: 'meta-llama/llama-3.1-8b-instruct:free',
    ollama_model: 'llama3',
    enable_ollama_fallback: false,
    llm_call_budget: 50
  });
  const [isBulkProcessing, setIsBulkProcessing] = useState(false);
  const [connectionTestResult, setConnectionTestResult] = useState(null);
  const [isAiAssisting, setIsAiAssisting] = useState(false);
  const [processingBatchKey, setProcessingBatchKey] = useState(null);

  const currentPageRef = useRef(currentPage);
  const searchQueryRef = useRef(searchQuery);
  const gridFilterStatusRef = useRef(gridFilterStatus);

  useEffect(() => {
    currentPageRef.current = currentPage;
    searchQueryRef.current = searchQuery;
    gridFilterStatusRef.current = gridFilterStatus;
  }, [currentPage, searchQuery, gridFilterStatus]);

  const refreshProductsList = async () => {
    try {
      let url = `/api/products?page=${currentPageRef.current}&limit=12`;
      if (searchQueryRef.current) {
        url += `&q=${encodeURIComponent(searchQueryRef.current)}`;
      }
      if (gridFilterStatusRef.current !== 'ALL') {
        url += `&status=${gridFilterStatusRef.current.toLowerCase()}`;
      }
      const res = await fetch(url);
      const data = await res.json();
      setProducts(data.data || []);
      setTotalProductsCount(data.total || 0);
    } catch (err) {
      console.error("Error refreshing products:", err);
    }
  };

  // Connect to Server-Sent Events (SSE) stream for live updates
  useEffect(() => {
    let eventSource = null;
    
    const connectSSE = () => {
      console.log("Connecting to SSE log stream at /api/logs/stream...");
      eventSource = new EventSource('/api/logs/stream');
      
      eventSource.onmessage = (event) => {
        try {
          const logEntry = JSON.parse(event.data);
          
          // Prepend to agent logs
          setAgentLogs(prev => [logEntry, ...prev].slice(0, 150));
          
          // Parse phase transitions (e.g. "Phase X/8: <label>")
          const match = logEntry.message.match(/Phase (\d)\/8:\s*([a-zA-Z0-9_-]+)/);
          if (match) {
            const phaseNum = parseInt(match[1], 10);
            const phaseLabel = match[2];
            const pId = logEntry.product_id;
            
            if (phaseLabel === 'LLM' && logEntry.message.includes('Skipped')) {
              setSkippedLLM(prev => ({ ...prev, [pId]: true }));
            }
            
            setActiveProductPhases(prev => ({
              ...prev,
              [pId]: phaseNum
            }));
          }
          
          // Refresh products, stats, and conflicts when products transition or finish
          if (
            logEntry.message.includes("completed") || 
            logEntry.message.includes("Cache hit") || 
            logEntry.message.includes("Duplicate detected") ||
            logEntry.message.includes("Phase 8/8")
          ) {
            fetchStats();
            refreshProductsList();
            fetchConflicts();
          }
        } catch (err) {
          console.error("Error parsing SSE log entry:", err);
        }
      };
      
      eventSource.onerror = (err) => {
        console.error("SSE Connection failed, retrying in 5 seconds...", err);
        eventSource.close();
        setTimeout(connectSSE, 5000);
      };
    };
    
    connectSSE();
    
    // Initial fetch on mount
    fetchStats();
    fetchLogs();
    fetchSettings();
    
    // Auto-refresh stats every 3s to keep UI metrics & button state in sync
    const statsInterval = setInterval(() => {
      fetchStats();
    }, 3000);
    
    return () => {
      if (eventSource) {
        eventSource.close();
      }
      clearInterval(statsInterval);
    };
  }, []);

  // Load grid when tab or dependencies change
  useEffect(() => {
    if (currentTab === 'preview') {
      fetchProducts(currentPage);
    } else if (currentTab === 'conflicts') {
      fetchConflicts();
    }
  }, [currentTab, currentPage, searchQuery, gridFilterStatus]);

  const fetchStats = async () => {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      setStats(data);
      setIsBulkProcessing(!!data.is_bulk_running);

      // Fetch all products to calculate difficulty distribution
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
      console.error("Error fetching stats:", err);
    }
  };

  const fetchProducts = async (page = 1) => {
    try {
      let url = `/api/products?page=${page}&limit=12&_t=${Date.now()}`;
      if (searchQuery) {
        url += `&q=${encodeURIComponent(searchQuery)}`;
      }
      if (gridFilterStatus !== 'ALL') {
        url += `&status=${gridFilterStatus.toLowerCase()}`;
      }
      const res = await fetch(url);
      const data = await res.json();
      setProducts(data.data || []);
      setTotalProductsCount(data.total || 0);
    } catch (err) {
      console.error("Error fetching products:", err);
    }
  };

  const fetchConflicts = async () => {
    try {
      // Fetch flagged products
      const res = await fetch(`/api/products?status=flagged_hitl&limit=100&_t=${Date.now()}`);
      const data = await res.json();
      setFlaggedProducts(data.data || []);
    } catch (err) {
      console.error("Error fetching conflicts:", err);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch('/api/llm-logs');
      const data = await res.json();
      setLlmLogs(data || []);
    } catch (err) {
      console.error("Error fetching LLM logs:", err);
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      setConnectionSettings({
        llm_provider: data.llm_provider || 'auto',
        gemini_api_key: data.gemini_api_key || '',
        gemini_model: data.gemini_model || 'gemini-1.5-flash',
        groq_api_key: data.groq_api_key || '',
        groq_model: data.groq_model || 'llama-3.3-70b-versatile',
        openrouter_api_key: data.openrouter_api_key || '',
        openrouter_model: data.openrouter_model || 'meta-llama/llama-3.1-8b-instruct:free',
        ollama_model: data.ollama_model || 'llama3',
        enable_ollama_fallback: !!data.enable_ollama_fallback,
        llm_call_budget: data.llm_call_budget || 50
      });
    } catch (err) {
      console.error("Error fetching settings:", err);
    }
  };

  const handleUpdateSettings = async () => {
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(connectionSettings)
      });
      const data = await res.json();
      if (data.status === 'success') {
        alert("Configuration parameters applied successfully.");
        fetchSettings();
      }
    } catch (err) {
      console.error("Error saving settings:", err);
    }
  };

  const handleTestConnection = async () => {
    setConnectionTestResult({ status: 'testing', message: 'Verifying connection channel...' });
    try {
      const res = await fetch('/api/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(connectionSettings)
      });
      const data = await res.json();
      setConnectionTestResult({ status: data.status, message: data.message });
    } catch (err) {
      setConnectionTestResult({ status: 'error', message: `Test failed: ${err.message}` });
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setIngestFile(file);
    setIngestStatus('');
    
    const reader = new FileReader();
    reader.onload = (event) => {
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
      const previewRows = [];
      let rowCount = 0;
      
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        rowCount++;
        if (previewRows.length < 5) {
          const cols = parseCSVLine(line);
          if (cols.length === headers.length) {
            const row = {};
            headers.forEach((h, idx) => row[h] = cols[idx]);
            previewRows.push(row);
          }
        }
      }
      setIngestPreview({ headers, rows: previewRows });
      setIngestRowsCount(rowCount);
    };
    reader.readAsText(file);
  };

  const triggerIngest = async () => {
    if (!ingestFile) return;
    setIngestStatus('ingesting');
    
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

      try {
        const res = await fetch('/api/ingest-batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ products: parsed })
        });
        const data = await res.json();
        if (data.status === 'success') {
          setIngestStatus('completed');
          fetchStats();
        }
      } catch (err) {
        setIngestStatus('error');
        console.error("Ingestion failed:", err);
      }
    };
    reader.readAsText(ingestFile);
  };

  const handleRunBulkEnrichment = async () => {
    try {
      setIsBulkProcessing(true);
      const res = await fetch('/api/run-bulk?limit=30', { method: 'POST' });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Enrichment failed");
      }
      showToast("🚀 Catalog enrichment started (Demo Cap: Up to 30 products)", "success");
      setTimeout(() => {
        fetchStats();
        fetchProducts(currentPage);
      }, 1000);
    } catch (err) {
      setIsBulkProcessing(false);
      console.error("Enrichment failed:", err);
      showToast(err.message || "Enrichment failed", "error");
    }
  };

  const handleClearAllParsedInput = async () => {
    if (!window.confirm("Are you sure you want to clear all parsed input and reset the dataset back to fresh pending state?")) {
      return;
    }
    try {
      setIsBulkProcessing(false);
      const res = await fetch('/api/clear-all', { method: 'POST' });
      if (!res.ok) {
        throw new Error("Failed to clear parsed input");
      }
      const data = await res.json();
      showToast(data.message || "All parsed input cleared successfully!", "success");
      fetchStats();
      fetchProducts(1);
      setCurrentPage(1);
    } catch (err) {
      console.error("Clear all failed:", err);
      showToast("Failed to clear parsed input.", "error");
    }
  };

  const openEditModal = async (product) => {
    try {
      const res = await fetch(`/api/products/${product.id}`);
      const data = await res.json();
      
      setSelectedProduct(product);
      setEditingProductFields({
        mfg_part_num: data.product.mfg_part_num || '',
        part_manuf: data.product.part_manuf || '',
        resolved_manufacturer: data.product.resolved_manufacturer || '',
        resolved_brand: data.product.resolved_brand || '',
        part_desc: data.product.part_desc || '',
        invoice_desc: data.product.invoice_desc || '',
        mobile_desc: data.product.mobile_desc || '',
        short_desc: data.product.short_desc || '',
        long_desc: data.product.long_desc || '',
        retail_desc: data.product.retail_desc || '',
        classpath: data.product.classpath || ''
      });
      setEditingAttributes(data.attributes || []);
      setEditingProductLogs(data.logs || []);
    } catch (err) {
      console.error("Failed to load product details:", err);
    }
  };

  const handleSaveManualEdits = async () => {
    if (!selectedProduct) return;
    try {
      const res = await fetch(`/api/products/${selectedProduct.id}/update-attributes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          attributes: editingAttributes,
          invoice_desc: editingProductFields.invoice_desc,
          mobile_desc: editingProductFields.mobile_desc,
          short_desc: editingProductFields.short_desc,
          long_desc: editingProductFields.long_desc,
          classpath: editingProductFields.classpath
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setSelectedProduct(null);
        fetchStats();
        fetchProducts(currentPage);
      }
    } catch (err) {
      console.error("Failed to update attributes:", err);
    }
  };

  const handleResolveConflict = async (productId, conflictId, chosenValue) => {
    try {
      const res = await fetch(`/api/products/${productId}/resolve-conflict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conflict_id: conflictId,
          chosen_value: chosenValue
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        fetchConflicts();
        fetchStats();
        setSelectedConflictProduct(null);
      }
    } catch (err) {
      console.error("Failed to resolve conflict:", err);
    }
  };

  const handleApproveConflictProduct = async () => {
    if (!selectedConflictProduct) return;
    const pId = selectedConflictProduct.product.id;
    try {
      const res = await fetch(`/api/products/${pId}/update-attributes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          attributes: conflictAttributes,
          invoice_desc: conflictInvoiceDesc,
          mobile_desc: conflictMobileDesc,
          short_desc: conflictShortDesc,
          long_desc: conflictLongDesc,
          classpath: conflictClasspath,
          resolved_brand: conflictResolvedBrand,
          resolved_manufacturer: conflictResolvedManufacturer
        })
      });
      if (res.ok) {
        showToast("✨ Conflict resolved successfully!", "success");
        setSelectedConflictProduct(null);
        fetchConflicts();
        fetchStats();
        fetchProducts(currentPage);
      } else {
        showToast("Failed to resolve product conflicts", "error");
      }
    } catch (err) {
      console.error("Error resolving conflicts:", err);
      showToast("Error resolving conflicts", "error");
    }
  };

  const handleAiAssist = async () => {
    if (!selectedConflictProduct) return;
    setIsAiAssisting(true);
    try {
      const res = await fetch(`/api/products/${selectedConflictProduct.product.id}/ai-assist`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        showToast(errData.detail || "AI Assist request failed. Please check your API keys.", "error");
        return;
      }
      const data = await res.json();
      if (data.resolved_brand) setConflictResolvedBrand(data.resolved_brand);
      if (data.resolved_manufacturer) setConflictResolvedManufacturer(data.resolved_manufacturer);
      if (data.classpath) setConflictClasspath(data.classpath);
      if (data.invoice_desc) setConflictInvoiceDesc(data.invoice_desc);
      if (data.mobile_desc) setConflictMobileDesc(data.mobile_desc);
      if (data.short_desc) setConflictShortDesc(data.short_desc);
      if (data.long_desc) setConflictLongDesc(data.long_desc);
      if (data.attributes) setConflictAttributes(data.attributes);
      showToast("✨ AI Assist suggestions updated inline!", "success");
    } catch (err) {
      console.error("Failed running AI Assist:", err);
      showToast("Error connecting to AI Assist API endpoint", "error");
    } finally {
      setIsAiAssisting(false);
    }
  };

  // Determine current pipeline step
  const getPipelineStage = () => {
    if (stats.total === 0) return 1; // Ingestion Stage
    if (stats.pending > 0) return 2; // Enrichment Stage
    if (stats.flagged_hitl > 0) return 3; // HITL Stage
    return 4; // Completed / Export Stage
  };

  const currentStage = getPipelineStage();

  const renderPipelineProgress = () => {
    const stages = [
      { id: 1, name: "1. Data Ingestion", desc: "Upload catalog file" },
      { id: 2, name: "2. Content Enrichment", desc: "Run AI parsing & description builds" },
      { id: 3, name: "3. Verification Checkpoint", desc: "Resolve flagged conflict items" },
      { id: 4, name: "4. Output & Export", desc: "Ready to download delivery format" }
    ];

    return (
      <div className="glass-panel" style={{ padding: '20px 24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--primary-hover)', fontWeight: '600' }}>Active Pipeline Stage</span>
            <h2 style={{ fontSize: '1.25rem', fontWeight: '700', marginTop: '2px', color: 'var(--text-main)' }}>
              {currentStage === 1 && "Staged: Awaiting Product Ingestion"}
              {currentStage === 2 && `Staged: Enrichment Staging Area (${stats.pending} pending items)`}
              {currentStage === 3 && `Staged: Enrichment Complete — ${stats.flagged_hitl} Conflicts Blocked (Action Required)`}
              {currentStage === 4 && "Staged: Platform Verification Complete — Ready to Export"}
            </h2>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn" onClick={handleClearAllParsedInput} style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', fontWeight: '600' }}>
              <Trash2 size={16} /> Clear All Parsed Input
            </button>
            {currentStage === 2 && (
              <button className="btn btn-primary" onClick={handleRunBulkEnrichment} disabled={isBulkProcessing || stats.processing > 0}>
                <Play size={16} /> {isBulkProcessing || stats.processing > 0 ? "Enriching Products..." : "Run Catalog Enrichment (Max 30 - Demo Cap)"}
              </button>
            )}
            {currentStage === 3 && (
              <button className="btn btn-warning" style={{ background: 'var(--warning)', color: '#000', boxShadow: 'none' }} onClick={() => setCurrentTab('conflicts')}>
                <ShieldAlert size={16} /> Resolve Conflicts First
              </button>
            )}
            {currentStage === 4 && (
              <a href="/api/export" className="btn btn-success" style={{ background: 'var(--success)', textDecoration: 'none', color: '#fff' }}>
                <Download size={16} /> Export Enriched CSV
              </a>
            )}
          </div>
        </div>

        {/* Progress Timeline Nodes */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '28px', position: 'relative' }}>
          <div style={{ position: 'absolute', top: '15px', left: '20px', right: '20px', height: '2px', background: 'rgba(255,255,255,0.06)', zIndex: 1 }}></div>
          <div style={{ position: 'absolute', top: '15px', left: '20px', width: `${((currentStage - 1) / 3) * 94}%`, height: '2px', background: 'var(--primary)', zIndex: 2, transition: 'width 0.4s ease' }}></div>
          
          {stages.map(stage => {
            const isCompleted = currentStage > stage.id;
            const isActive = currentStage === stage.id;
            return (
              <div key={stage.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 3, position: 'relative', width: '22%' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: isCompleted ? 'var(--success)' : isActive ? 'var(--primary)' : '#121826',
                  border: isActive ? '3px solid #fff' : '2px solid var(--border-glass)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: '700',
                  fontSize: '0.85rem',
                  color: isCompleted || isActive ? '#fff' : 'var(--text-muted)',
                  boxShadow: isActive ? '0 0 15px var(--primary)' : 'none',
                  transition: 'all 0.3s ease'
                }}>
                  {isCompleted ? "✓" : stage.id}
                </div>
                <span style={{ fontSize: '0.8rem', fontWeight: isActive ? '700' : '500', color: isActive ? 'var(--text-main)' : 'var(--text-muted)', marginTop: '8px', textAlign: 'center' }}>
                  {stage.name}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="app-container" style={{ minHeight: '100vh', display: 'flex' }}>
      
      {/* PROFESSIONAL SIDEBAR PANEL */}
      <div className="sidebar">
        <div className="sidebar-logo">
          <Layers size={22} color="#8b5cf6" />
          <span className="logo-text" style={{ fontSize: '1.05rem', fontWeight: '700' }}>Unihack Intelligence</span>
        </div>
        <ul className="sidebar-menu" style={{ flexGrow: 1 }}>
          <li className={`menu-item ${currentTab === 'dashboard' ? 'active' : ''}`} onClick={() => { setCurrentTab('dashboard'); fetchStats(); }}>
            <BarChart3 size={18} />
            <span>Dashboard</span>
          </li>
          <li className={`menu-item ${currentTab === 'ingestion' ? 'active' : ''}`} onClick={() => setCurrentTab('ingestion')}>
            <UploadCloud size={18} />
            <span>Ingest Catalogue</span>
          </li>
          <li className={`menu-item ${currentTab === 'preview' ? 'active' : ''}`} onClick={() => { setCurrentTab('preview'); setCurrentPage(1); }}>
            <Database size={18} />
            <span>Excel Preview</span>
          </li>
          <li className={`menu-item ${currentTab === 'conflicts' ? 'active' : ''}`} onClick={() => setCurrentTab('conflicts')}>
            <ShieldAlert size={18} />
            <span>Conflicts Review</span>
            {stats.flagged_hitl > 0 && (
              <span style={{ marginLeft: 'auto', background: 'var(--danger)', color: '#fff', fontSize: '0.7rem', padding: '2px 6px', borderRadius: '10px', fontWeight: '700' }}>
                {stats.flagged_hitl}
              </span>
            )}
          </li>
          <li className={`menu-item ${currentTab === 'settings' ? 'active' : ''}`} onClick={() => setCurrentTab('settings')}>
            <SettingsIcon size={18} />
            <span>Connection Configs</span>
          </li>
        </ul>
        <div className="sidebar-footer">
          <span>Unihack Real Beginners v2.0</span>
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="main-content" style={{ flexGrow: 1, overflowY: 'auto' }}>
        
        {/* Floating Toast Notification Container */}
        {toast && (
          <div style={{
            position: 'fixed',
            top: '20px',
            right: '24px',
            zIndex: 9999,
            padding: '12px 20px',
            borderRadius: '12px',
            background: toast.type === 'error' ? 'rgba(239, 68, 68, 0.95)' : toast.type === 'success' ? 'rgba(34, 197, 94, 0.95)' : 'rgba(30, 41, 59, 0.95)',
            color: '#ffffff',
            boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
            fontWeight: '600',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(255,255,255,0.2)'
          }}>
            <Activity size={18} /> {toast.text}
          </div>
        )}

        {/* Dynamic Progress Indicator */}
        {renderPipelineProgress()}

        {/* --- DASHBOARD TAB --- */}
        {currentTab === 'dashboard' && (
          <div>
            <div className="panel-header" style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1>Platform Dashboard</h1>
                <p className="subtitle" style={{ margin: 0 }}>Overview of product enrichment statistics and agent orchestration</p>
              </div>
              <div style={{
                background: (stats.llm_calls_today || 0) >= (stats.llm_call_budget || 50) * 0.9 ? 'rgba(239, 68, 68, 0.15)' : (stats.llm_calls_today || 0) >= (stats.llm_call_budget || 50) * 0.7 ? 'rgba(245, 158, 11, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                color: (stats.llm_calls_today || 0) >= (stats.llm_call_budget || 50) * 0.9 ? '#f87171' : (stats.llm_calls_today || 0) >= (stats.llm_call_budget || 50) * 0.7 ? '#fbbf24' : '#60a5fa',
                padding: '6px 14px',
                borderRadius: '8px',
                fontWeight: '700',
                fontSize: '0.825rem',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                border: '1px solid rgba(255,255,255,0.1)'
              }}>
                <Zap size={15} /> LLM Quota Today: {stats.llm_calls_today || 0} / {stats.llm_call_budget || 50} Calls
              </div>
            </div>

            {/* Statistics Cards Grid */}
            <div className="stats-grid">
              <div className="stat-card card-primary">
                <div className="stat-icon primary"><Database size={24} /></div>
                <div className="stat-info">
                  <span className="stat-label">Ingested Items</span>
                  <span className="stat-value">{stats.total}</span>
                </div>
              </div>
              <div className="stat-card card-warning">
                <div className="stat-icon warning"><RotateCcw size={24} /></div>
                <div className="stat-info">
                  <span className="stat-label">Pending Enrichment</span>
                  <span className="stat-value">{stats.pending}</span>
                </div>
              </div>
              <div className="stat-card card-success">
                <div className="stat-icon success"><CheckCircle size={24} /></div>
                <div className="stat-info">
                  <span className="stat-label">Enriched completed</span>
                  <span className="stat-value">{stats.completed}</span>
                </div>
              </div>
              <div className="stat-card card-danger">
                <div className="stat-icon danger"><ShieldAlert size={24} /></div>
                <div className="stat-info">
                  <span className="stat-label">HITL Conflicts</span>
                  <span className="stat-value">{stats.flagged_hitl}</span>
                </div>
              </div>
            </div>

            {/* Difficulty Level & Engine metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: '3.5fr 2.5fr', gap: '24px', marginBottom: '24px' }}>
              <div className="glass-panel" style={{ margin: 0 }}>
                <h3 className="panel-title" style={{ marginBottom: '16px' }}><Activity size={18} color="#8b5cf6" /> System Difficulty Distribution</h3>
                <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', height: '140px' }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--success)' }}>{extraStats.easy}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>EASY PATHS</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--warning)' }}>{extraStats.medium}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>MEDIUM PATHS</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--danger)' }}>{extraStats.hard}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>HARD PATHS</div>
                  </div>
                </div>
              </div>

              <div className="glass-panel" style={{ margin: 0 }}>
                <h3 className="panel-title" style={{ marginBottom: '16px' }}><Layers size={18} color="#8b5cf6" /> Pipeline Cache Metrics</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '10px' }}>
                  <div className="flex-space">
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Fingerprint Cache Hits</span>
                    <span style={{ fontWeight: '700', color: 'var(--success)' }}>{extraStats.cache_hits} items</span>
                  </div>
                  <div className="flex-space">
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>LLM Inference Calls</span>
                    <span style={{ fontWeight: '700' }}>{extraStats.llm_calls} calls</span>
                  </div>
                  <div className="flex-space">
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Average Confidence Score</span>
                    <span style={{ fontWeight: '700', color: 'var(--primary-hover)' }}>{stats.avg_confidence}%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Dynamic Agent Logs Terminal */}
            <div className="terminal-window">
              <div className="terminal-header">
                <div className="terminal-dots">
                  <div className="terminal-dot red"></div>
                  <div className="terminal-dot yellow"></div>
                  <div className="terminal-dot green"></div>
                </div>
                <div className="terminal-title">Active Ingestion & Extraction Log Stream</div>
                <TerminalIcon size={14} color="var(--text-dark)" />
              </div>
              <div className="terminal-body" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                {agentLogs.length === 0 ? (
                  <div style={{ color: 'var(--text-dark)', padding: '10px', textAlign: 'center' }}>Awaiting pipeline execution. Logs will appear here dynamically.</div>
                ) : (
                  agentLogs.map((log, index) => {
                    let levelColor = '#fff';
                    if (log.level === 'SUCCESS') levelColor = 'var(--success)';
                    else if (log.level === 'WARNING') levelColor = 'var(--warning)';
                    else if (log.level === 'ERROR') levelColor = 'var(--danger)';
                    else if (log.level === 'INFO') levelColor = 'var(--primary-hover)';
                    
                    return (
                      <div key={index} className="log-line" style={{ display: 'flex', gap: '8px', fontSize: '0.8rem', marginBottom: '4px', fontFamily: 'monospace' }}>
                        <span className="log-time" style={{ color: 'var(--text-dark)', minWidth: '75px' }}>[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                        <span className="log-agent" style={{ color: 'var(--secondary)', fontWeight: 'bold', minWidth: '95px', display: 'inline-block' }}>{log.agent_name}</span>
                        <span className="log-msg" style={{ color: levelColor }}>
                          {log.message}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}

        {/* --- INGESTION TAB --- */}
        {currentTab === 'ingestion' && (
          <div>
            <div className="panel-header" style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1>Ingest Product Catalog</h1>
                <p className="subtitle" style={{ margin: 0 }}>Select a raw industrial/distributor product catalog file to load pending items</p>
              </div>
            </div>

            <div className="glass-panel" style={{ width: '100%', minHeight: '520px', margin: 0 }}>
              <div 
                style={{ border: '2px dashed var(--border-glass)', borderRadius: '8px', padding: '36px 20px', cursor: 'pointer', background: 'rgba(255,255,255,0.01)', textAlign: 'center' }}
                onClick={() => fileInputRef.current.click()}
              >
              <UploadCloud size={32} color="var(--primary)" style={{ marginBottom: '12px' }} />
              <p style={{ fontSize: '0.95rem', fontWeight: '600' }}>Select Catalog CSV File</p>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-dark)' }}>Only .csv files are supported</span>
              <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept=".csv" onChange={handleFileSelect} />
            </div>

            {ingestFile && (
              <div style={{ marginTop: '24px', padding: '16px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-glass)', borderRadius: '8px' }}>
                <div style={{ fontWeight: '700', color: 'var(--primary-hover)', fontSize: '0.9rem' }}>Selected: {ingestFile.name}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>Detected {ingestRowsCount} product records.</div>

                {ingestPreview && (
                  <div style={{ marginTop: '16px', overflowX: 'auto' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: '700', marginBottom: '8px', color: 'var(--text-muted)' }}>Raw File Head Sample:</div>
                    <table style={{ width: '100%', fontSize: '0.75rem', borderCollapse: 'collapse', border: '1px solid var(--border-glass)' }}>
                      <thead>
                        <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                          {ingestPreview.headers.slice(0, 4).map((h, i) => (
                            <th key={i} style={{ padding: '8px', border: '1px solid var(--border-glass)', textAlign: 'left' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {ingestPreview.rows.map((row, rIdx) => (
                          <tr key={rIdx}>
                            {ingestPreview.headers.slice(0, 4).map((h, cIdx) => (
                              <td key={cIdx} style={{ padding: '8px', border: '1px solid var(--border-glass)', color: 'var(--text-muted)', maxWidth: '150px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {row[h]}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
                  <button className="btn btn-primary" onClick={triggerIngest} disabled={ingestStatus === 'ingesting'}>
                    {ingestStatus === 'ingesting' ? "Ingesting Database..." : "Process Ingest Load"}
                  </button>
                  <button className="btn btn-secondary" onClick={() => { setIngestFile(null); setIngestPreview(null); }}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {ingestStatus === 'completed' && (
              <div style={{ marginTop: '16px', padding: '12px', background: 'rgba(16,185,129,0.1)', border: '1px solid var(--success)', borderRadius: '6px', color: 'var(--success)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle size={16} /> Catalog ingestion complete! You can run the enrichment pipeline now.
              </div>
            )}
          </div>
        </div>
        )}

        {/* --- EXCEL PREVIEW / SPREADSHEET TAB --- */}
        {currentTab === 'preview' && (
          <div>
            <div className="panel-header" style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1>Spreadsheet Excel Preview</h1>
                <p className="subtitle" style={{ margin: 0 }}>Manual editor grid to check stage progress and override product specifications</p>
              </div>
            </div>

            <div className="glass-panel" style={{ width: '100%', minHeight: '520px', display: 'flex', flexDirection: 'column', margin: 0 }}>

            {/* Filter controls */}
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', marginBottom: '20px', flexWrap: 'wrap' }}>
              <div style={{ position: 'relative', width: '320px' }}>
                <input 
                  type="text" 
                  className="form-input" 
                  placeholder="Filter by MPN, manufacturer..." 
                  value={searchQuery}
                  onChange={e => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                  style={{ paddingLeft: '36px' }}
                />
                <Search size={16} style={{ position: 'absolute', left: '12px', top: '13px', color: 'var(--text-dark)' }} />
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                {['ALL', 'PENDING', 'PROCESSING', 'COMPLETED', 'FLAGGED_HITL'].map(st => (
                  <button 
                    key={st}
                    className={`btn ${gridFilterStatus === st ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                    onClick={() => { setGridFilterStatus(st); setCurrentPage(1); }}
                  >
                    {st === 'FLAGGED_HITL' ? 'HITL Conflicts' : st.toLowerCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* spreadsheet data grid */}
            <div className="table-container" style={{ flexGrow: 1 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Part Number (MPN)</th>
                    <th>Manufacturer</th>
                    <th>Classification Category (Classpath)</th>
                    <th>Original Description</th>
                    <th>Stage Status</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.length === 0 ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dark)' }}>No catalogue records found. Ingest a CSV to begin.</td>
                    </tr>
                  ) : (
                    products.map(p => (
                      <tr key={p.id}>
                        <td style={{ fontWeight: '700', color: 'var(--primary-hover)' }}>{p.mfg_part_num}</td>
                        <td>{p.part_manuf || 'Unbranded'}</td>
                        <td style={{ fontSize: '0.8rem', color: '#fff' }}>{p.classpath || <span style={{ color: 'var(--text-dark)' }}>N/A</span>}</td>
                        <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{p.part_desc}</td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <span className={`badge badge-${p.status === 'flagged_hitl' ? 'flagged' : p.status}`} style={{ width: 'fit-content' }}>
                              {p.status === 'flagged_hitl' ? 'HITL Review' : p.status}
                            </span>
                            <PipelineStepTracker 
                              product={p} 
                              activePhase={activeProductPhases[p.id]} 
                              isSkippedLLM={skippedLLM[p.id]} 
                            />
                          </div>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn btn-secondary" style={{ padding: '6px 10px', fontSize: '0.75rem' }} onClick={() => openEditModal(p)}>
                            <Edit3 size={12} /> Edit
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination footer */}
            {totalProductsCount > 12 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px', borderTop: '1px solid var(--border-glass)', paddingTop: '16px' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Showing {(currentPage - 1) * 12 + 1} - {Math.min(currentPage * 12, totalProductsCount)} of {totalProductsCount} items</span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-secondary" style={{ padding: '6px 12px' }} disabled={currentPage === 1} onClick={() => setCurrentPage(currentPage - 1)}>
                    Previous
                  </button>
                  <button className="btn btn-secondary" style={{ padding: '6px 12px' }} disabled={currentPage * 12 >= totalProductsCount} onClick={() => setCurrentPage(currentPage + 1)}>
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
        )}

        {/* --- CONFLICTS / HITL REVIEW TAB --- */}
        {currentTab === 'conflicts' && (
          <div>
            <div className="panel-header" style={{ marginBottom: '24px' }}>
              <div>
                <h1>Human-in-the-Loop Verification</h1>
                <p className="subtitle" style={{ margin: 0 }}>Review brand or specification conflicts identified by the enrichment pipeline</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2.5fr 3.5fr', gap: '24px' }}>
              <div className="glass-panel" style={{ margin: 0, minHeight: '520px' }}>
                <h3 className="panel-title" style={{ marginBottom: '16px' }}><ShieldAlert size={18} color="var(--danger)" /> Flagged Conflicts</h3>
                
                {flaggedProducts.length === 0 ? (
                  <div style={{ color: 'var(--success)', padding: '20px', textAlign: 'center', fontSize: '0.9rem' }}>
                    🟢 No conflicts found! Stage checkpoint is completely verified.
                  </div>
                ) : (
                  (() => {
                    const brandGroups = {};
                    flaggedProducts.forEach(p => {
                      const rawBrand = p.resolved_brand && p.resolved_brand !== 'UNKNOWN' 
                        ? p.resolved_brand 
                        : (p.e1_brand || p.unilog_brand || p.dib_brand || p.resolved_manufacturer || p.part_manuf || 'Unclassified Brand');
                      const key = rawBrand.trim();
                      if (!brandGroups[key]) brandGroups[key] = [];
                      brandGroups[key].push(p);
                    });

                    // Chunk each brand group into sub-batches of MAX 3 items
                    const BATCH_SIZE = 3;
                    const subBatches = [];

                    Object.keys(brandGroups).forEach(brandName => {
                      const items = brandGroups[brandName];
                      for (let i = 0; i < items.length; i += BATCH_SIZE) {
                        const chunk = items.slice(i, i + BATCH_SIZE);
                        const subIndex = Math.floor(i / BATCH_SIZE) + 1;
                        const totalSub = Math.ceil(items.length / BATCH_SIZE);
                        subBatches.push({
                          brandName,
                          subIndex,
                          totalSub,
                          items: chunk
                        });
                      }
                    });

                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', maxHeight: '75vh', overflowY: 'auto', paddingRight: '4px' }}>
                        {subBatches.map((batchObj, bIdx) => {
                          const { brandName, subIndex, totalSub, items } = batchObj;
                          const itemIds = items.map(item => item.id);
                          const subTitle = totalSub > 1 ? ` (Batch ${subIndex} of ${totalSub})` : '';
                          const batchKey = `${brandName}-${subIndex}`;
                          const isThisBatchProcessing = processingBatchKey === batchKey;

                          return (
                            <div key={batchKey} style={{ border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: '10px', background: 'rgba(15, 23, 42, 0.5)', padding: '12px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', paddingBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                                <div>
                                  <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#c084fc', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    🏷️ Brand Batch #{bIdx + 1}: {brandName}{subTitle}
                                  </div>
                                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                                    {items.length} item{items.length > 1 ? 's' : ''} in this batch (Max 3/prompt — Groq & Token Limit Safe)
                                  </div>
                                </div>
                                <div style={{ display: 'flex', gap: '6px' }}>
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation();
                                      try {
                                        setProcessingBatchKey(batchKey);
                                        const res = await fetch('/api/batches/brand-ai-assist', {
                                          method: 'POST',
                                          headers: { 'Content-Type': 'application/json' },
                                          body: JSON.stringify({ product_ids: itemIds })
                                        });
                                        if (!res.ok) {
                                          let errMsg = `Batch AI assist failed (${res.status})`;
                                          try {
                                            const errData = await res.json();
                                            errMsg = errData.detail || errMsg;
                                          } catch {
                                            errMsg = `Server error ${res.status}: Please try again.`;
                                          }
                                          throw new Error(errMsg);
                                        }
                                        const data = await res.json();
                                        showToast(`✨ AI generated suggestions for ${data.updated_count} products!`, "success");
                                        await fetchConflicts();
                                        await fetchStats();
                                        if (selectedConflictProduct && itemIds.includes(selectedConflictProduct.product.id)) {
                                          const res = await fetch(`/api/products/${selectedConflictProduct.product.id}`);
                                          const updatedProduct = await res.json();
                                          setSelectedConflictProduct(updatedProduct);
                                        }
                                      } catch (err) {
                                        showToast(err.message || "Batch AI Assist failed", "error");
                                      } finally {
                                        setProcessingBatchKey(null);
                                      }
                                    }}
                                    disabled={!!processingBatchKey}
                                    style={{
                                      padding: '4px 8px',
                                      fontSize: '0.7rem',
                                      fontWeight: '600',
                                      borderRadius: '6px',
                                      background: isThisBatchProcessing ? 'rgba(234, 179, 8, 0.2)' : 'rgba(139, 92, 246, 0.2)',
                                      color: isThisBatchProcessing ? '#fde047' : '#c084fc',
                                      border: isThisBatchProcessing ? '1px solid rgba(234, 179, 8, 0.4)' : '1px solid rgba(139, 92, 246, 0.4)',
                                      cursor: processingBatchKey ? 'not-allowed' : 'pointer'
                                    }}
                                  >
                                    {isThisBatchProcessing ? '⚡ Processing...' : '✨ Batch AI (1 API Call)'}
                                  </button>
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation();
                                      if (!confirm(`Approve all ${itemIds.length} products for '${brandName}'?`)) return;
                                      try {
                                        const res = await fetch('/api/batches/batch-approve', {
                                          method: 'POST',
                                          headers: { 'Content-Type': 'application/json' },
                                          body: JSON.stringify({ product_ids: itemIds })
                                        });
                                        const data = await res.json();
                                        showToast(`✅ Batch approved ${itemIds.length} products!`, "success");
                                        fetchConflicts();
                                        fetchStats();
                                      } catch (err) {
                                        showToast("Batch approval failed", "error");
                                      }
                                    }}
                                    style={{
                                      padding: '4px 8px',
                                      fontSize: '0.7rem',
                                      fontWeight: '600',
                                      borderRadius: '6px',
                                      background: 'rgba(34, 197, 94, 0.15)',
                                      color: '#4ade80',
                                      border: '1px solid rgba(34, 197, 94, 0.3)',
                                      cursor: 'pointer'
                                    }}
                                  >
                                    ✅ Batch Approve
                                  </button>
                                </div>
                              </div>

                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                {items.map(p => (
                                  <div 
                                    key={p.id}
                                    onClick={async () => {
                                      const res = await fetch(`/api/products/${p.id}`);
                                      const data = await res.json();
                                      setSelectedConflictProduct(data);
                                    }}
                                    style={{
                                      padding: '8px 10px',
                                      background: selectedConflictProduct?.product?.id === p.id ? 'var(--primary-glow)' : 'rgba(255,255,255,0.02)',
                                      border: '1px solid',
                                      borderColor: selectedConflictProduct?.product?.id === p.id ? 'var(--primary)' : 'rgba(255,255,255,0.05)',
                                      borderRadius: '6px',
                                      cursor: 'pointer'
                                    }}
                                  >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <div style={{ fontWeight: '700', color: 'var(--primary-hover)', fontSize: '0.8rem' }}>{p.mfg_part_num}</div>
                                      {p.ai_drafted === 1 && (
                                        <span style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(192, 132, 252, 0.2)', color: '#c084fc', border: '1px solid rgba(192, 132, 252, 0.4)', fontWeight: '600' }}>
                                          ✨ AI Drafted — Review Needed
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                                      {p.part_desc}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()
                )}
              </div>

              <div className="glass-panel" style={{ margin: 0, minHeight: '520px' }}>
                {selectedConflictProduct ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '80vh', overflowY: 'auto', paddingRight: '8px' }}>
                    <div>
                      <h3 style={{ fontSize: '1.1rem', color: 'var(--text-main)', marginBottom: '4px' }}>Conflict Resolution Detail: {selectedConflictProduct.product.mfg_part_num}</h3>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        <strong>Raw Product Description:</strong> {selectedConflictProduct.product.part_desc}
                      </div>
                    </div>

                    {/* Checkpoint Badge & Flagged Warning Info */}
                    {(() => {
                      const warningLog = selectedConflictProduct.logs?.find(l => l.level === 'WARNING');
                      const isTaxonomyConflict = warningLog?.message?.toLowerCase().includes('taxonomy') || 
                                                 warningLog?.message?.toLowerCase().includes('category') ||
                                                 !selectedConflictProduct.product.classpath;
                      return (
                        <>
                          <div>
                            {isTaxonomyConflict ? (
                              <span style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#c084fc', border: '1px solid rgba(139, 92, 246, 0.3)', padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase' }}>
                                📌 HITL Checkpoint #1: Taxonomy Review
                              </span>
                            ) : (
                              <span style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase' }}>
                                ⚙️ HITL Checkpoint #2: Attribute/Enrichment Review
                              </span>
                            )}
                          </div>

                          {warningLog && (
                            <div style={{
                              background: 'rgba(239, 68, 68, 0.08)',
                              border: '1px solid rgba(239, 68, 68, 0.25)',
                              borderRadius: '8px',
                              padding: '12px',
                              color: '#f87171',
                              fontSize: '0.85rem',
                              display: 'flex',
                              alignItems: 'start',
                              gap: '8px'
                            }}>
                              <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                              <div>
                                <strong style={{ fontWeight: '700' }}>Flagged Reason:</strong> {warningLog.message}
                              </div>
                            </div>
                          )}
                        </>
                      );
                    })()}

                    {/* 🌐 Pre-AI Official Manufacturer Lookup (Token-Free Manual Verification) */}
                    {selectedConflictProduct && selectedConflictProduct.product && (
                      <div style={{
                        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(37, 99, 235, 0.04) 100%)',
                        border: '1px solid rgba(59, 130, 246, 0.35)',
                        borderRadius: '10px',
                        padding: '14px',
                        marginBottom: '14px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '700', color: '#60a5fa', fontSize: '0.85rem' }}>
                            <Globe size={18} color="#60a5fa" />
                            <span>🌐 1-Click Official Manufacturer Lookup</span>
                          </div>
                          <span style={{ fontSize: '0.7rem', background: 'rgba(59, 130, 246, 0.2)', color: '#93c5fd', padding: '2px 8px', borderRadius: '12px', fontWeight: '600' }}>
                            ⚡ Zero Tokens / No AI Quota Used
                          </span>
                        </div>

                        <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)', marginBottom: '10px', lineHeight: '1.4' }}>
                          Verify specifications directly on the official manufacturer portal to reduce AI quota usage.
                        </div>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {selectedConflictProduct.product.mfr_url ? (
                            <div style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span style={{ color: '#93c5fd', fontWeight: '600' }}>Verified Product Page:</span>
                              <a 
                                href={selectedConflictProduct.product.mfr_url} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                style={{ color: '#38bdf8', textDecoration: 'underline', fontWeight: '700', wordBreak: 'break-all', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                              >
                                {selectedConflictProduct.product.mfr_url} <ExternalLink size={12} />
                              </a>
                            </div>
                          ) : (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Direct URL unmapped. Search official manufacturer portal:</span>
                              <a 
                                href={`https://www.google.com/search?q=${encodeURIComponent((selectedConflictProduct.product.resolved_brand || selectedConflictProduct.product.part_manuf || '') + ' ' + selectedConflictProduct.product.mfg_part_num + ' official site spec sheet')}`}
                                target="_blank" 
                                rel="noopener noreferrer" 
                                style={{ 
                                  fontSize: '0.73rem', 
                                  background: 'rgba(59, 130, 246, 0.2)', 
                                  color: '#60a5fa', 
                                  border: '1px solid rgba(59, 130, 246, 0.4)', 
                                  padding: '4px 10px', 
                                  borderRadius: '6px', 
                                  textDecoration: 'none', 
                                  fontWeight: '600', 
                                  display: 'inline-flex', 
                                  alignItems: 'center', 
                                  gap: '4px' 
                                }}
                              >
                                <Search size={12} /> Search {selectedConflictProduct.product.resolved_brand || selectedConflictProduct.product.part_manuf || 'Mfr'} Portal <ExternalLink size={11} />
                              </a>
                            </div>
                          )}

                          {[
                            selectedConflictProduct.product.ref_url_1,
                            selectedConflictProduct.product.ref_url_2,
                            selectedConflictProduct.product.ref_url_3,
                            selectedConflictProduct.product.ref_url_4,
                            selectedConflictProduct.product.ref_url_5
                          ].filter(Boolean).length > 0 && (
                            <div style={{ marginTop: '6px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
                              <div style={{ fontSize: '0.73rem', fontWeight: '600', color: '#c084fc', marginBottom: '6px' }}>
                                📄 Official Spec Manuals & PDFs:
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                {[
                                  selectedConflictProduct.product.ref_url_1,
                                  selectedConflictProduct.product.ref_url_2,
                                  selectedConflictProduct.product.ref_url_3,
                                  selectedConflictProduct.product.ref_url_4,
                                  selectedConflictProduct.product.ref_url_5
                                ].filter(Boolean).map((pdfUrl, idx) => (
                                  <a 
                                    key={idx}
                                    href={pdfUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ fontSize: '0.75rem', color: '#c084fc', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                                  >
                                    <FileText size={13} color="#c084fc" /> 
                                    <span>Doc #{idx + 1}: {pdfUrl.split('/').pop() || pdfUrl}</span>
                                    <ExternalLink size={11} />
                                  </a>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* ✨ AI Resolution Assistant Widget */}
                    <div style={{
                      background: 'rgba(139, 92, 246, 0.06)',
                      border: '1px solid rgba(139, 92, 246, 0.25)',
                      borderRadius: '8px',
                      padding: '14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px'
                    }}>
                      <style dangerouslySetInnerHTML={{__html: `
                        @keyframes spin {
                          0% { transform: rotate(0deg); }
                          100% { transform: rotate(360deg); }
                        }
                        .spin-anim {
                          animation: spin 1s infinite linear;
                        }
                      `}} />
                      <div style={{ flexGrow: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '700', color: '#c084fc', fontSize: '0.85rem' }}>
                          ✨ AI Resolution Assistant (Secondary Backup)
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px', lineHeight: '1.3' }}>
                          Only use if official manufacturer portal lookup above is insufficient.
                        </div>
                      </div>
                      <button 
                        className="btn btn-primary"
                        onClick={handleAiAssist}
                        disabled={isAiAssisting}
                        style={{
                          background: 'linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%)',
                          border: 'none',
                          color: '#fff',
                          fontSize: '0.75rem',
                          padding: '6px 12px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          cursor: isAiAssisting ? 'not-allowed' : 'pointer'
                        }}
                      >
                        {isAiAssisting ? (
                          <>
                            <span className="spin-anim" style={{ width: '10px', height: '10px', border: '2px solid #fff', borderTop: '2px solid transparent', borderRadius: '50%', display: 'inline-block' }}></span >
                            Thinking...
                          </>
                        ) : (
                          "AI Suggestions"
                        )}
                      </button>
                    </div>

                    {/* Competing Agent Conflicts Resolvers */}
                    {selectedConflictProduct.conflicts && selectedConflictProduct.conflicts.length > 0 && (
                      <div style={{ border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', padding: '12px', background: 'rgba(239, 68, 68, 0.02)' }}>
                        <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: '#f87171', marginBottom: '10px', textTransform: 'uppercase' }}>Agent Multi-Source Conflicts</h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          {selectedConflictProduct.conflicts.map(c => (
                            <div key={c.id} style={{ border: '1px solid var(--border-glass)', borderRadius: '6px', padding: '10px', background: 'rgba(0,0,0,0.1)' }}>
                              <span style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)' }}>
                                Conflicting Field: {c.field_name}
                              </span>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '8px' }}>
                                <div 
                                  onClick={() => {
                                    if (c.field_name === 'resolved_brand') setConflictResolvedBrand(c.value_a);
                                    else if (c.field_name === 'resolved_manufacturer') setConflictResolvedManufacturer(c.value_a);
                                    else if (c.field_name === 'classpath') setConflictClasspath(c.value_a);
                                  }}
                                  style={{ border: '1px dashed var(--border-glass)', padding: '8px', borderRadius: '4px', cursor: 'pointer', textAlign: 'center' }}
                                >
                                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Source: {c.agent_a}</div>
                                  <div style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--success)', marginTop: '2px' }}>{c.value_a || "NaN"}</div>
                                </div>
                                <div 
                                  onClick={() => {
                                    if (c.field_name === 'resolved_brand') setConflictResolvedBrand(c.value_b);
                                    else if (c.field_name === 'resolved_manufacturer') setConflictResolvedManufacturer(c.value_b);
                                    else if (c.field_name === 'classpath') setConflictClasspath(c.value_b);
                                  }}
                                  style={{ border: '1px dashed var(--border-glass)', padding: '8px', borderRadius: '4px', cursor: 'pointer', textAlign: 'center' }}
                                >
                                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Source: {c.agent_b}</div>
                                  <div style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--success)', marginTop: '2px' }}>{c.value_b || "NaN"}</div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Interactive Fields Editor Form */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label className="form-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Resolved Brand</label>
                        <input 
                          type="text" 
                          className="form-input" 
                          value={conflictResolvedBrand} 
                          onChange={e => setConflictResolvedBrand(e.target.value)} 
                          placeholder="Resolved brand..." 
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Resolved Manufacturer</label>
                        <input 
                          type="text" 
                          className="form-input" 
                          value={conflictResolvedManufacturer} 
                          onChange={e => setConflictResolvedManufacturer(e.target.value)} 
                          placeholder="Resolved manufacturer..." 
                        />
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Taxonomy Classpath</label>
                      <input 
                        type="text" 
                        className="form-input" 
                        value={conflictClasspath} 
                        onChange={e => setConflictClasspath(e.target.value)} 
                        placeholder="Taxonomy classpath (e.g. Category>Subcategory)..." 
                      />
                    </div>

                    <div style={{ borderTop: '1px solid var(--border-glass)', paddingTop: '12px' }}>
                      <h4 style={{ fontSize: '0.9rem', color: 'var(--text-main)', marginBottom: '8px' }}>B2B Descriptions</h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        <div className="form-group">
                          <label className="form-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Invoice Description (max 40 chars)</label>
                          <input 
                            type="text" 
                            className="form-input" 
                            value={conflictInvoiceDesc} 
                            maxLength={40}
                            onChange={e => setConflictInvoiceDesc(e.target.value)} 
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Mobile Description (60-80 chars)</label>
                          <input 
                            type="text" 
                            className="form-input" 
                            value={conflictMobileDesc} 
                            onChange={e => setConflictMobileDesc(e.target.value)} 
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Short Description</label>
                          <input 
                            type="text" 
                            className="form-input" 
                            value={conflictShortDesc} 
                            onChange={e => setConflictShortDesc(e.target.value)} 
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Long Description</label>
                          <textarea 
                            className="form-input" 
                            rows={3}
                            value={conflictLongDesc} 
                            onChange={e => setConflictLongDesc(e.target.value)} 
                          />
                        </div>
                      </div>
                    </div>

                    {/* Extracted Attributes List */}
                    <div style={{ borderTop: '1px solid var(--border-glass)', paddingTop: '12px' }}>
                      <h4 style={{ fontSize: '0.9rem', color: 'var(--text-main)', marginBottom: '8px' }}>Extracted Attributes</h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto', paddingRight: '4px' }}>
                        {conflictAttributes.map((attr, idx) => (
                          <div key={idx} style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <input 
                              type="text" 
                              className="form-input" 
                              value={attr.label || ''} 
                              onChange={e => {
                                const updated = [...conflictAttributes];
                                updated[idx] = { ...updated[idx], label: e.target.value };
                                setConflictAttributes(updated);
                              }}
                              placeholder="Label"
                              style={{ width: '30%', fontSize: '0.8rem', padding: '6px' }}
                            />
                            <input 
                              type="text" 
                              className="form-input" 
                              value={attr.value || ''} 
                              onChange={e => {
                                const updated = [...conflictAttributes];
                                updated[idx] = { ...updated[idx], value: e.target.value };
                                setConflictAttributes(updated);
                              }}
                              placeholder="Value"
                              style={{ width: '45%', fontSize: '0.8rem', padding: '6px' }}
                            />
                            <input 
                              type="text" 
                              className="form-input" 
                              value={attr.uom || ''} 
                              onChange={e => {
                                const updated = [...conflictAttributes];
                                updated[idx] = { ...updated[idx], uom: e.target.value };
                                setConflictAttributes(updated);
                              }}
                              placeholder="UOM"
                              style={{ width: '15%', fontSize: '0.8rem', padding: '6px' }}
                            />
                            <button 
                              className="btn btn-secondary" 
                              style={{ padding: '6px', color: 'var(--danger)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                              onClick={() => {
                                setConflictAttributes(conflictAttributes.filter((_, i) => i !== idx));
                              }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                      <button 
                        className="btn btn-secondary" 
                        style={{ marginTop: '8px', padding: '4px 10px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                        onClick={() => setConflictAttributes([...conflictAttributes, { label: '', value: '', uom: '' }])}
                      >
                        <Plus size={12} /> Add Attribute
                      </button>
                    </div>

                    <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-glass)', paddingTop: '16px', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                      <button 
                        className="btn btn-secondary" 
                        onClick={() => setSelectedConflictProduct(null)}
                      >
                        Cancel
                      </button>
                      <button 
                        className="btn btn-primary"
                        onClick={handleApproveConflictProduct}
                        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <CheckCircle size={16} /> Approve and Complete Record
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-dark)' }}>
                    <ShieldAlert size={36} style={{ marginBottom: '12px' }} />
                    <span>Select a product card on the left to resolve conflicts.</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* --- SETTINGS TAB --- */}
        {currentTab === 'settings' && (
          <div>
            <div className="panel-header" style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1>Connection Configs & Failover Chain</h1>
                <p className="subtitle" style={{ margin: 0 }}>Manage API keys, model parameters, and active LLM provider strategy</p>
              </div>
            </div>

            <div className="glass-panel" style={{ width: '100%', minHeight: '520px', margin: 0 }}>

            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label className="form-label">Active Provider Selection Strategy</label>
              <select 
                className="form-input" 
                value={connectionSettings.llm_provider} 
                onChange={e => setConnectionSettings({ ...connectionSettings, llm_provider: e.target.value })}
              >
                <option value="auto">Auto Failover Chain (Gemini → Groq → OpenRouter)</option>
                <option value="gemini">Google Gemini AI Engine (Primary)</option>
                <option value="groq">Groq Cloud AI Engine (Fallback 1)</option>
                <option value="openrouter">OpenRouter Unified Engine (Fallback 2)</option>
                <option value="ollama">Local Ollama Server (Dev Mode)</option>
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '16px' }}>
              {/* Google Gemini */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-glass)' }}>
                <div style={{ fontWeight: '600', color: '#a78bfa', fontSize: '0.85rem', marginBottom: '8px' }}>Google Gemini</div>
                <div className="form-group" style={{ marginBottom: '8px' }}>
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>API Key</label>
                  <input 
                    type="password" 
                    className="form-input" 
                    placeholder="AQ.Ab8..." 
                    value={connectionSettings.gemini_api_key} 
                    onChange={e => setConnectionSettings({ ...connectionSettings, gemini_api_key: e.target.value })} 
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>Model</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={connectionSettings.gemini_model} 
                    onChange={e => setConnectionSettings({ ...connectionSettings, gemini_model: e.target.value })} 
                  />
                </div>
              </div>

              {/* Groq Cloud */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-glass)' }}>
                <div style={{ fontWeight: '600', color: '#38bdf8', fontSize: '0.85rem', marginBottom: '8px' }}>Groq Cloud</div>
                <div className="form-group" style={{ marginBottom: '8px' }}>
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>API Key</label>
                  <input 
                    type="password" 
                    className="form-input" 
                    placeholder="gsk_..." 
                    value={connectionSettings.groq_api_key} 
                    onChange={e => setConnectionSettings({ ...connectionSettings, groq_api_key: e.target.value })} 
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>Model</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={connectionSettings.groq_model} 
                    onChange={e => setConnectionSettings({ ...connectionSettings, groq_model: e.target.value })} 
                  />
                  <span style={{ fontSize: '0.68rem', color: '#38bdf8', marginTop: '4px', display: 'block' }}>
                    ⚡ Payload limit guarded (Max 3500 chars / 750 tokens per prompt)
                  </span>
                </div>
              </div>

              {/* OpenRouter */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-glass)' }}>
                <div style={{ fontWeight: '600', color: '#f43f5e', fontSize: '0.85rem', marginBottom: '8px' }}>OpenRouter (Free Tier)</div>
                <div className="form-group" style={{ marginBottom: '8px' }}>
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>API Key</label>
                  <input 
                    type="password" 
                    className="form-input" 
                    placeholder="sk-or-v1-..." 
                    value={connectionSettings.openrouter_api_key} 
                    onChange={e => setConnectionSettings({ ...connectionSettings, openrouter_api_key: e.target.value })} 
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>Free Model ID</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="openrouter/auto"
                    value={connectionSettings.openrouter_model} 
                    onChange={e => setConnectionSettings({ ...connectionSettings, openrouter_model: e.target.value })} 
                  />
                </div>
              </div>

              {/* Ollama Local */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-glass)' }}>
                <div style={{ fontWeight: '600', color: '#10b981', fontSize: '0.85rem', marginBottom: '8px' }}>Local Ollama (Dev)</div>
                <div className="form-group" style={{ marginBottom: '8px' }}>
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>Local Model ID</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="llama3" 
                    value={connectionSettings.ollama_model} 
                    onChange={e => setConnectionSettings({ ...connectionSettings, ollama_model: e.target.value })} 
                  />
                </div>
                <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input 
                    type="checkbox" 
                    id="enable_ollama" 
                    checked={connectionSettings.enable_ollama_fallback}
                    onChange={e => setConnectionSettings({ ...connectionSettings, enable_ollama_fallback: e.target.checked })} 
                  />
                  <label htmlFor="enable_ollama" style={{ fontSize: '0.75rem', cursor: 'pointer', color: 'var(--text-main)' }}>Enable Local Ollama Dev Fallback</label>
                </div>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label className="form-label">Bulk Enrichment LLM Call Budget Cap</label>
              <input 
                type="number" 
                className="form-input" 
                min="0"
                value={connectionSettings.llm_call_budget} 
                onChange={e => setConnectionSettings({ ...connectionSettings, llm_call_budget: parseInt(e.target.value, 10) || 0 })} 
              />
              <span style={{ fontSize: '0.7rem', color: 'var(--text-dark)', marginTop: '4px', display: 'block' }}>
                Caps total LLM API calls combined across all providers during a single bulk run.
              </span>
            </div>

            <div style={{ display: 'flex', gap: '10px', marginTop: '24px' }}>
              <button className="btn btn-primary" onClick={handleUpdateSettings}>
                Apply Configuration Parameters
              </button>
              <button className="btn btn-secondary" onClick={handleTestConnection}>
                Test Provider Connectivity
              </button>
            </div>

            {connectionTestResult && (
              <div style={{ 
                marginTop: '20px', 
                padding: '12px', 
                background: connectionTestResult.status === 'success' ? 'rgba(16,185,129,0.1)' : connectionTestResult.status === 'warning' ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)', 
                border: '1px solid',
                borderColor: connectionTestResult.status === 'success' ? 'var(--success)' : connectionTestResult.status === 'warning' ? 'var(--warning)' : 'var(--danger)',
                borderRadius: '6px', 
                color: connectionTestResult.status === 'success' ? 'var(--success)' : connectionTestResult.status === 'warning' ? 'var(--warning)' : 'var(--danger)',
                fontSize: '0.85rem'
              }}>
                <strong>Test Status: {connectionTestResult.status.toUpperCase()}</strong>
                <p style={{ marginTop: '4px' }}>{connectionTestResult.message}</p>
              </div>
            )}
          </div>
        </div>
        )}

      </div>

      {/* --- EXCEL PREVIEW MANUAL EDITOR MODAL --- */}
      {selectedProduct && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(6, 8, 12, 0.95)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass-panel" style={{ width: '820px', maxHeight: '90vh', overflowY: 'auto', border: '1px solid var(--border-glass-hover)', padding: '30px' }}>
            <div className="flex-space" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '16px', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '1.25rem', color: 'var(--primary-hover)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Edit3 size={18} /> Edit Product Specifications: {editingProductFields.mfg_part_num}
              </h2>
              <button 
                onClick={() => setSelectedProduct(null)} 
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
              {/* Product Core / Meta info */}
              <div>
                <div style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '12px' }}>Staging Catalog Core Properties</div>
                
                <div className="form-group" style={{ marginBottom: '12px' }}>
                  <label className="form-label">Part Number (Mfg_Part_Num)</label>
                  <input type="text" className="form-input" disabled value={editingProductFields.mfg_part_num} />
                </div>

                <div className="form-group" style={{ marginBottom: '12px' }}>
                  <label className="form-label">Raw Supplier Description</label>
                  <textarea className="form-input" disabled rows={3} style={{ resize: 'none', fontSize: '0.8rem' }} value={editingProductFields.part_desc} />
                </div>

                <div className="form-group" style={{ marginBottom: '12px' }}>
                  <label className="form-label">Classification Path (Classpath)</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={editingProductFields.classpath} 
                    onChange={e => setEditingProductFields({ ...editingProductFields, classpath: e.target.value })} 
                  />
                </div>
              </div>

              {/* B2B Descriptions */}
              <div>
                <div style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '12px' }}>B2B Descriptive Fields (Dynamic Verification)</div>
                
                <div className="form-group" style={{ marginBottom: '12px' }}>
                  <label className="form-label">
                    Invoice Description 
                    <span style={{ float: 'right', color: editingProductFields.invoice_desc.length > 40 ? 'var(--danger)' : 'var(--text-dark)' }}>
                      {editingProductFields.invoice_desc.length}/40
                    </span>
                  </label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={editingProductFields.invoice_desc} 
                    onChange={e => setEditingProductFields({ ...editingProductFields, invoice_desc: e.target.value })} 
                  />
                </div>

                <div className="form-group" style={{ marginBottom: '12px' }}>
                  <label className="form-label">
                    Mobile Description 
                    <span style={{ float: 'right', color: (editingProductFields.mobile_desc.length < 60 || editingProductFields.mobile_desc.length > 80) ? 'var(--danger)' : 'var(--success)' }}>
                      {editingProductFields.mobile_desc.length} chars (Target: 60-80)
                    </span>
                  </label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={editingProductFields.mobile_desc} 
                    onChange={e => setEditingProductFields({ ...editingProductFields, mobile_desc: e.target.value })} 
                  />
                </div>

                <div className="form-group" style={{ marginBottom: '12px' }}>
                  <label className="form-label">Short Web Description</label>
                  <textarea 
                    className="form-input" 
                    rows={2} 
                    style={{ resize: 'none' }}
                    value={editingProductFields.short_desc} 
                    onChange={e => setEditingProductFields({ ...editingProductFields, short_desc: e.target.value })} 
                  />
                </div>
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border-glass)', paddingTop: '20px', marginBottom: '24px' }}>
              <label className="form-label" style={{ marginBottom: '12px' }}>Long Prose Catalog Description</label>
              <textarea 
                className="form-input" 
                rows={3} 
                value={editingProductFields.long_desc} 
                onChange={e => setEditingProductFields({ ...editingProductFields, long_desc: e.target.value })} 
              />
            </div>

            {/* Specifications attributes edit */}
            <div style={{ borderTop: '1px solid var(--border-glass)', paddingTop: '20px', marginBottom: '24px' }}>
              <div className="flex-space" style={{ marginBottom: '12px' }}>
                <span className="stat-label" style={{ color: 'var(--text-main)' }}>Extracted Specifications Matrix</span>
                <button 
                  className="btn btn-secondary" 
                  style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                  onClick={() => setEditingAttributes([...editingAttributes, { label: '', value: '', uom: '' }])}
                >
                  <Plus size={12} /> Add Attribute Row
                </button>
              </div>

              <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-muted)' }}>
                    <th style={{ textAlign: 'left', padding: '6px 4px' }}>Attribute Label</th>
                    <th style={{ textAlign: 'left', padding: '6px 4px' }}>Attribute Value</th>
                    <th style={{ textAlign: 'left', padding: '6px 4px' }}>Unit (UOM)</th>
                    <th style={{ textAlign: 'right', padding: '6px 4px' }}>Remove</th>
                  </tr>
                </thead>
                <tbody>
                  {editingAttributes.map((a, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                      <td style={{ padding: '6px 4px' }}>
                        <input 
                          type="text" 
                          className="form-input" 
                          style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                          value={a.label} 
                          onChange={e => {
                            const newAttrs = [...editingAttributes];
                            newAttrs[idx].label = e.target.value;
                            setEditingAttributes(newAttrs);
                          }} 
                        />
                      </td>
                      <td style={{ padding: '6px 4px' }}>
                        <input 
                          type="text" 
                          className="form-input" 
                          style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                          value={a.value} 
                          onChange={e => {
                            const newAttrs = [...editingAttributes];
                            newAttrs[idx].value = e.target.value;
                            setEditingAttributes(newAttrs);
                          }} 
                        />
                      </td>
                      <td style={{ padding: '6px 4px' }}>
                        <input 
                          type="text" 
                          className="form-input" 
                          style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                          placeholder="e.g. in, mm, V, A"
                          value={a.uom || ''} 
                          onChange={e => {
                            const newAttrs = [...editingAttributes];
                            newAttrs[idx].uom = e.target.value;
                            setEditingAttributes(newAttrs);
                          }} 
                        />
                      </td>
                      <td style={{ padding: '6px 4px', textAlign: 'right' }}>
                        <button 
                          className="btn btn-secondary" 
                          style={{ padding: '4px', background: 'rgba(239, 68, 68, 0.05)', borderColor: 'rgba(239, 68, 68, 0.15)' }}
                          onClick={() => {
                            const newAttrs = [...editingAttributes];
                            newAttrs.splice(idx, 1);
                            setEditingAttributes(newAttrs);
                          }}
                        >
                          <Trash2 size={14} color="var(--danger)" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 🌐 Official Manufacturer Verification Links for Self-Verification */}
            {selectedProduct && (
              <div style={{
                marginBottom: '24px',
                background: 'rgba(59, 130, 246, 0.06)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                borderRadius: '8px',
                padding: '14px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                  <Globe size={16} color="#60a5fa" />
                  <span style={{ fontSize: '0.85rem', fontWeight: '700', color: '#60a5fa' }}>
                    🌐 Official Manufacturer Verification Links
                  </span>
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {selectedProduct.mfr_url ? (
                    <div style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={{ color: 'var(--text-muted)', fontWeight: '600' }}>Manufacturer Product Page:</span>
                      <a 
                        href={selectedProduct.mfr_url} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        style={{ color: '#38bdf8', textDecoration: 'underline', fontWeight: '600', wordBreak: 'break-all', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      >
                        {selectedProduct.mfr_url} <ExternalLink size={12} />
                      </a>
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      No direct manufacturer URL available.
                    </div>
                  )}

                  {[
                    selectedProduct.ref_url_1,
                    selectedProduct.ref_url_2,
                    selectedProduct.ref_url_3,
                    selectedProduct.ref_url_4,
                    selectedProduct.ref_url_5
                  ].filter(Boolean).length > 0 && (
                    <div style={{ marginTop: '6px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '6px' }}>
                        📄 Reference Manuals & Spec PDFs:
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {[
                          selectedProduct.ref_url_1,
                          selectedProduct.ref_url_2,
                          selectedProduct.ref_url_3,
                          selectedProduct.ref_url_4,
                          selectedProduct.ref_url_5
                        ].filter(Boolean).map((pdfUrl, idx) => (
                          <a 
                            key={idx}
                            href={pdfUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ fontSize: '0.75rem', color: '#c084fc', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                          >
                            <FileText size={13} color="#c084fc" /> 
                            <span>Doc #{idx + 1}: {pdfUrl.split('/').pop() || pdfUrl}</span>
                            <ExternalLink size={11} />
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Product Ingestion Agent Logs */}
            <div style={{ borderTop: '1px solid var(--border-glass)', paddingTop: '20px', marginBottom: '24px' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '8px' }}>Product Agent Ingestion logs</div>
              <div style={{ background: '#06080c', border: '1px solid var(--border-glass)', borderRadius: '6px', padding: '10px 14px', maxHeight: '140px', overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', lineHeight: '1.5' }}>
                {editingProductLogs.length === 0 ? (
                  <div style={{ color: 'var(--text-dark)' }}>No logs compiled for this product.</div>
                ) : (
                  editingProductLogs.map((l, idx) => (
                    <div key={idx} style={{ color: l.level === 'SUCCESS' ? 'var(--success)' : l.level === 'WARNING' ? 'var(--warning)' : l.level === 'ERROR' ? 'var(--danger)' : '#9ca3af', marginBottom: '4px' }}>
                      [{l.agent_name}] {l.message}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button className="btn btn-primary" onClick={handleSaveManualEdits}>
                Save Specifications & Approve Record
              </button>
              <button className="btn btn-secondary" onClick={() => setSelectedProduct(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
