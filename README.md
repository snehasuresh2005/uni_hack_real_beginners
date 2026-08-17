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

## 🦙 Running with Local LLM (Ollama)

This project has built-in support for **Ollama**, allowing you to run attribute extraction locally and privately without requiring external API keys.

### 1. Install Ollama
Download and install Ollama for your operating system from the official website: [https://ollama.com](https://ollama.com).

### 2. Start the Ollama Server
Make sure the Ollama desktop application is running, or run the serve command in a terminal:
```powershell
ollama serve
```

### 3. Pull the LLM Model
By default, the application is configured to use the `llama3` model. Pull the model locally:
```powershell
ollama pull llama3
```
*Note: You can pull other models (e.g. `llama3.1`, `mistral`, `gemma2`) and change the model name in the settings panel of the web dashboard.*

### 4. Optional Configurations
If your Ollama server is running on a different port or host, you can set the `OLLAMA_BASE_URL` environment variable:
```powershell
$env:OLLAMA_BASE_URL="http://localhost:11434"
```

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

### Step 2: Configure LLM Provider
1. Click on the **Settings** cog in the top-right of the dashboard.
2. Select **Ollama** or **Gemini** as your LLM Provider.
   - If using **Gemini**, input your Google Gemini API Key.
   - If using **Ollama**, specify your local model name (e.g. `llama3`).
3. Save settings.

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
