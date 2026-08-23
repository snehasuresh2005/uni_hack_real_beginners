# B2B Product Intelligence & Content Enrichment Platform

An **AI-driven Product Attribute Extraction and Enrichment** platform designed to ingest raw industrial/distributor product catalogs, classify products into high-fidelity taxonomies, extract fine-grained specifications (attributes and units of measure) using LLMs, flag discrepancies for Human-in-the-Loop (HITL) resolution, and export clean data adhering to strict delivery formats.

---

## 🛠️ Architecture Overview

The system consists of two primary components:
1. **Backend (FastAPI)**: Serves the REST API, manages SQLite database connection/operations, and runs the LLM processing pipeline (utilizing the Google Gemini API or local Ollama server) for attribute extraction.
2. **Frontend (React + Vite)**: Provides a premium web dashboard with interactive tools for monitoring statistics, uploading product catalogs, reviewing extraction logs, resolving brand or attribute conflicts, and exporting data.

```
unihack_real_beginners/
├── backend/                  # FastAPI Application
│   ├── app.py                # API router and entry point
│   ├── database.py           # SQLite schema and DB initialization
│   ├── pipeline.py           # extraction logic (Gemini & Ollama)
│   ├── preload_data.py       # Data preloading script
│   └── requirements.txt      # Python dependencies
├── frontend/                 # Vite React App
│   ├── src/
│   │   ├── App.jsx           # Main React component containing dashboard UI
│   │   ├── index.css         # Styling system
│   │   └── main.jsx          # React entry point
│   └── package.json          # Node dependencies
├── README.md                 # Project guide (this file)
└── run_all.py                # Automated launcher script
```

---

## 🚀 Local Installation & Setup

### Prerequisites
Make sure you have python 3.10+ and Node.js 18+ installed on your system.

### 1. Install Dependencies
**Backend:**
```powershell
pip install -r backend/requirements.txt
```

**Frontend:**
```powershell
cd frontend
npm install
cd ..
```

---

## ⚡ Hosted Multi-Provider LLM Redundancy Chain (No GPU Required)

For production deployment on servers without local GPUs, the platform implements an automated multi-provider failover chain:
**Google Gemini (Primary) → Groq Cloud (Fallback 1) → OpenRouter (Fallback 2)**

If the primary provider hits rate limits (`429`), authentication errors (`401`/`403`), or model errors (`404`), the pipeline seamlessly switches to the next provider in the chain without failing the product extraction job.

### 🔑 Obtaining Free API Keys
- **Google Gemini**: Obtain a free key at [Google AI Studio](https://aistudio.google.com/app/apikey). Default model: `gemini-1.5-flash`
- **Groq Cloud**: Obtain a free key at [Groq Console](https://console.groq.com/keys). Default model: `llama-3.3-70b-versatile`
- **OpenRouter**: Obtain a free key at [OpenRouter Keys](https://openrouter.ai/keys). Default free model: `meta-llama/llama-3.1-8b-instruct:free`

### 🦙 Optional Local LLM (Ollama Dev Fallback)
For offline local development, you can optionally enable local **Ollama** as a dev fallback by setting `ENABLE_OLLAMA_FALLBACK=true` in settings or `.env`. Local Ollama is **not required** for production deployment.

---

## 🚀 Running the Platform

### Option A: Run Everything Automatically (Recommended)
To spin up both the FastAPI backend and Vite frontend dev server at once, run the automated launcher script:
```powershell
python run_all.py
```

- **Frontend Access**: Open [http://127.0.0.1:5173](http://127.0.0.1:5173) in your web browser.
- **Backend API Docs**: View FastAPI docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Option B: Run Individually (Separate Terminals)

**Start Backend (FastAPI):**
```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

**Start Frontend (Vite React):**
```powershell
cd frontend
npm run dev
```

---

## 📖 Step-by-Step Usage Flow

### Step 1: Ingestion
1. Click the **Ingest CSV** / **Upload** button in the dashboard.
2. Select your catalog CSV (e.g., `Unihack_ Sample Dataset - Input.csv`).
3. The platform parses the catalog, deduplicates on Manufacturer Part Number (`Mfg_Part_Num`), and loads the entries into the local database as `pending`.

### Step 2: Configure LLM Redundancy Chain
1. Click on the **Settings** cog in the top-right of the dashboard.
2. Select **Auto Failover Chain (Gemini → Groq → OpenRouter)** or explicitly select a single provider.
3. Provide your API keys for Gemini, Groq, and OpenRouter.
4. Save configuration and click **Test Provider Connectivity**.

### Step 3: Run Enrichment Pipeline
- **Single Product**: Click on a product card, open its detail view, and click **Run Enrichment**.
- **Bulk Process**: Click **Run Bulk Enrichment** to run extraction on a batch of pending products in the background.

The extraction pipeline will:
1. Classify the product's taxonomy path (Classpath).
2. Extract specifications (e.g., Voltage, Material, Sizes) and isolate their value and **Unit of Measure (UOM)**.
3. Automatically write audit trail messages to **Agent Logs**.
4. Generate B2B descriptive attributes (`INVOICE_DESC`, `MOBILE_DESC`, `SHORT_DESC`, `LONG_DESC1`, `RETAIL_DESC`).

### Step 4: Resolve Brand/Attribute Conflicts
If brand values differ across multiple source fields (like `E1_Brand` vs `Unilog_Brand` vs `DIB_Brand`), or if the LLM identifies conflicting data points, the product is flagged as `flagged_hitl`.
1. Go to the **Conflicts** tab in the dashboard.
2. Select a flagged product to review the conflicting options.
3. Choose the correct ground truth value or type a manual correction.
4. Click **Resolve** to save it.

### Step 5: Export Enriched Data
Once products are set to `completed`:
1. Click the **Export CSV** button in the dashboard header.
2. This downloads an enriched CSV conforming to the exact schema found in `Unihack_ Expected Output - Delivery Format.csv`.

---

## 🗄️ Database Schema & Structure

The SQLite database file is located at `backend/database.db` and is initialized automatically. It consists of four relational tables:

### 1. `products`
Stores product core details, taxonomy categories, B2B descriptions, and current ingestion/enrichment status.

### 2. `attributes`
Stores extracted specifications mapped to parent products.

### 3. `conflicts`
Tracks unresolved conflicting data points requiring human intervention.

### 4. `agent_logs`
Logs background pipeline lifecycle steps for human auditing.
