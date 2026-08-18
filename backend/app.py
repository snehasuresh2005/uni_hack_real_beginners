import os
import csv
import io
import sqlite3
import pandas as pd
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from datetime import datetime

from backend.database import get_db_connection, init_db
from backend.pipeline import run_pipeline_for_product, run_bulk_enrichment

# Initialize database
init_db()

app = FastAPI(title="AI Product Intelligence API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionSettings(BaseModel):
    llm_provider: str
    gemini_api_key: Optional[str] = ""
    ollama_model: Optional[str] = "llama3"
    llm_call_budget: int = 50

class IngestBatchRequest(BaseModel):
    products: List[dict]

import json

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

def load_settings():
    defaults = {
        "llm_provider": os.environ.get("LLM_PROVIDER", "gemini"),
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "llama3"),
        "llm_call_budget": int(os.environ.get("LLM_CALL_BUDGET", "50"))
    }
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                saved = json.load(f)
                return {**defaults, **saved}
        except Exception:
            return defaults
    return defaults

def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print("Failed to save settings to file:", e)

SETTINGS = load_settings()

@app.get("/api/stats")
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    total = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    pending = cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'pending'").fetchone()[0]
    processing = cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'processing'").fetchone()[0]
    flagged = cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'flagged_hitl'").fetchone()[0]
    completed = cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'completed'").fetchone()[0]
    
    avg_conf = cursor.execute("SELECT AVG(confidence_score) FROM products WHERE status != 'pending'").fetchone()[0] or 0.0
    
    conn.close()
    
    return {
        "total": total,
        "pending": pending,
        "processing": processing,
        "flagged_hitl": flagged,
        "completed": completed,
        "avg_confidence": round(avg_conf * 100, 1)
    }

@app.get("/api/products")
def list_products(status: Optional[str] = None, q: Optional[str] = None, page: int = 1, limit: int = 20):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    if q:
        query += " AND (mfg_part_num LIKE ? OR part_desc LIKE ? OR part_manuf LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        
    # Count total for pagination
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total = cursor.execute(count_query, params).fetchone()[0]
    
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, (page - 1) * limit])
    
    products = cursor.execute(query, params).fetchall()
    conn.close()
    
    return {
        "data": [dict(p) for p in products],
        "total": total,
        "page": page,
        "limit": limit
    }

@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    product = cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
        
    attributes = cursor.execute("SELECT * FROM attributes WHERE product_id = ?", (product_id,)).fetchall()
    logs = cursor.execute("SELECT * FROM agent_logs WHERE product_id = ? ORDER BY id ASC", (product_id,)).fetchall()
    conflicts = cursor.execute("SELECT * FROM conflicts WHERE product_id = ?", (product_id,)).fetchall()
    
    conn.close()
    
    return {
        "product": dict(product),
        "attributes": [dict(a) for a in attributes],
        "logs": [dict(l) for l in logs],
        "conflicts": [dict(c) for c in conflicts]
    }

# Concurrency locks for background tasks
IS_BULK_RUNNING = False
PROCESSING_PRODUCTS = set()

@app.post("/api/products/{product_id}/run")
def trigger_enrichment(product_id: int, background_tasks: BackgroundTasks):
    if product_id in PROCESSING_PRODUCTS:
        raise HTTPException(status_code=400, detail="This product is already being enriched.")
        
    key = SETTINGS.get("gemini_api_key")
    provider = SETTINGS.get("llm_provider", "gemini")
    model = SETTINGS.get("ollama_model", "llama3")
    
    def enrich_wrapper():
        try:
            PROCESSING_PRODUCTS.add(product_id)
            run_pipeline_for_product(product_id, key, provider, model)
        finally:
            PROCESSING_PRODUCTS.discard(product_id)
            
    background_tasks.add_task(enrich_wrapper)
    return {"status": "processing", "message": f"Enrichment pipeline started ({provider})"}

@app.post("/api/run-bulk")
def run_bulk(background_tasks: BackgroundTasks, limit: int = 10, llm_call_budget: Optional[int] = None):
    global IS_BULK_RUNNING
    if IS_BULK_RUNNING:
        raise HTTPException(status_code=400, detail="A bulk enrichment task is already running in the background.")
        
    key = SETTINGS.get("gemini_api_key")
    provider = SETTINGS.get("llm_provider", "gemini")
    model = SETTINGS.get("ollama_model", "llama3")
    budget = SETTINGS.get("llm_call_budget", 50) if llm_call_budget is None else llm_call_budget
    
    def bulk_wrapper():
        global IS_BULK_RUNNING
        try:
            run_bulk_enrichment(key, provider, model, limit, budget)
        finally:
            IS_BULK_RUNNING = False
            
    IS_BULK_RUNNING = True
    background_tasks.add_task(bulk_wrapper)
    return {"status": "processing", "message": f"Bulk enrichment for up to {limit} products started with an LLM budget of {budget} ({provider})"}

class ResolveConflictRequest(BaseModel):
    conflict_id: int
    chosen_value: str

@app.post("/api/products/{product_id}/resolve-conflict")
def resolve_conflict(product_id: int, req: ResolveConflictRequest):
    conn = get_db_connection()
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()
    
    conflict = cursor.execute("SELECT * FROM conflicts WHERE id = ?", (req.conflict_id,)).fetchone()
    if not conflict:
        conn.close()
        raise HTTPException(status_code=404, detail="Conflict not found")
        
    # Mark resolved
    cursor.execute("UPDATE conflicts SET resolved = 1 WHERE id = ?", (req.conflict_id,))
    
    # Update value in attributes table
    # Standardize UOM splitting if chosen value contains UOM
    field = conflict["field_name"]
    val = req.chosen_value
    uom = ""
    if " " in val:
        parts = val.split(" ")
        if len(parts) == 2 and parts[1] in ["in", "mm", "V", "A", "dBA", "RPM"]:
            val = parts[0]
            uom = parts[1]
            
    # Check if attribute already exists
    existing = cursor.execute("SELECT id FROM attributes WHERE product_id = ? AND label = ?", (product_id, field)).fetchone()
    if existing:
        cursor.execute(
            "UPDATE attributes SET value = ?, uom = ?, confidence = 1.0, source = 'Human In The Loop' WHERE id = ?",
            (val, uom, existing["id"])
        )
    else:
        cursor.execute(
            "INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation) VALUES (?, ?, ?, ?, 1.0, 'Human In The Loop', 'HITL Manual resolution')",
            (product_id, field, val, uom)
        )
        
    # Check if all conflicts for this product are resolved
    remaining = cursor.execute("SELECT COUNT(*) FROM conflicts WHERE product_id = ? AND resolved = 0", (product_id,)).fetchone()[0]
    if remaining == 0:
        cursor.execute("UPDATE products SET status = 'completed', confidence_score = 1.0 WHERE id = ?", (product_id,))
        
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Conflict resolved successfully"}

class UpdateAttributesRequest(BaseModel):
    attributes: List[dict] # list of {label, value, uom}
    invoice_desc: Optional[str] = None
    mobile_desc: Optional[str] = None
    short_desc: Optional[str] = None
    long_desc: Optional[str] = None
    classpath: Optional[str] = None

@app.post("/api/products/{product_id}/update-attributes")
def update_attributes(product_id: int, req: UpdateAttributesRequest):
    conn = get_db_connection()
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()
    
    # Save attributes
    for attr in req.attributes:
        label = attr["label"]
        value = attr["value"]
        uom = attr.get("uom", "")
        
        existing = cursor.execute("SELECT id FROM attributes WHERE product_id = ? AND label = ?", (product_id, label)).fetchone()
        if existing:
            cursor.execute(
                "UPDATE attributes SET value = ?, uom = ?, confidence = 1.0, source = 'Human In The Loop' WHERE id = ?",
                (value, uom, existing["id"])
            )
        else:
            cursor.execute(
                "INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation) VALUES (?, ?, ?, ?, 1.0, 'Human In The Loop', 'HITL Manual correction')",
                (product_id, label, value, uom)
            )
            
    # Save B2B descriptive fields
    cursor.execute(
        """UPDATE products 
        SET invoice_desc = ?, mobile_desc = ?, short_desc = ?, long_desc = ?, classpath = ?,
            status = 'completed', confidence_score = 1.0 
        WHERE id = ?""",
        (req.invoice_desc, req.mobile_desc, req.short_desc, req.long_desc, req.classpath, product_id)
    )
    
    # Clear conflicts
    cursor.execute("UPDATE conflicts SET resolved = 1 WHERE product_id = ?", (product_id,))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Attributes updated and product set to completed"}

@app.post("/api/ingest")
async def ingest_csv(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))
    
    # Check required columns
    required = ["Mfg_Part_Num", "Part_Desc"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {', '.join(missing)}")
        
    conn = get_db_connection()
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()
    
    # Pre-fetch existing MPNs into a set for O(1) lookups during ingestion
    existing_mpns = set(row[0] for row in cursor.execute("SELECT mfg_part_num FROM products").fetchall())
    
    count = 0
    now = datetime.now().isoformat()
    for _, row in df.iterrows():
        mpn = str(row["Mfg_Part_Num"])
        desc = str(row["Part_Desc"])
        e1 = str(row.get("E1_Brand", ""))
        unilog = str(row.get("Unilog_Brand", ""))
        dib = str(row.get("DIB_Brand", ""))
        manuf = str(row.get("Part_Manuf", ""))
        
        # Deduplication Guard using fast set check
        if mpn not in existing_mpns:
            cursor.execute(
                """INSERT INTO products 
                (mfg_part_num, part_desc, e1_brand, unilog_brand, dib_brand, part_manuf, status, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (mpn, desc, e1, unilog, dib, manuf, now, now)
            )
            existing_mpns.add(mpn)
            count += 1
            
    conn.commit()
    conn.close()
    
    return {"status": "success", "imported": count, "message": f"Successfully ingested {count} new products"}

@app.post("/api/ingest-batch")
def ingest_batch(req: IngestBatchRequest):
    conn = get_db_connection()
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()
    
    # Pre-fetch existing MPNs into a set for O(1) lookups during ingestion
    existing_mpns = set(row[0] for row in cursor.execute("SELECT mfg_part_num FROM products").fetchall())
    
    count = 0
    now = datetime.now().isoformat()
    for row in req.products:
        mpn = str(row.get("Mfg_Part_Num", row.get("mfg_part_num", ""))).strip()
        desc = str(row.get("Part_Desc", row.get("part_desc", ""))).strip()
        if not mpn or not desc or mpn == "nan" or desc == "nan":
            continue
            
        from backend.preprocessing.cleaner import normalize_placeholder
        e1 = normalize_placeholder(row.get("E1_Brand", ""))
        unilog = normalize_placeholder(row.get("Unilog_Brand", ""))
        dib = normalize_placeholder(row.get("DIB_Brand", ""))
        manuf = str(row.get("Part_Manuf", row.get("part_manuf", "")))
        
        # Deduplication Guard using fast set check
        if mpn not in existing_mpns:
            cursor.execute(
                """INSERT INTO products 
                (mfg_part_num, part_desc, e1_brand, unilog_brand, dib_brand, part_manuf, status, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (mpn, desc, e1, unilog, dib, manuf, now, now)
            )
            existing_mpns.add(mpn)
            count += 1
        else:
            cursor.execute(
                """UPDATE products 
                SET part_desc = ?, e1_brand = ?, unilog_brand = ?, dib_brand = ?, part_manuf = ?, status = 'pending', updated_at = ? 
                WHERE mfg_part_num = ?""",
                (desc, e1, unilog, dib, manuf, now, mpn)
            )
            # Find the internal ID and clean its attributes to prevent stale/cached pollution
            p_id_row = cursor.execute("SELECT id FROM products WHERE mfg_part_num = ?", (mpn,)).fetchone()
            if p_id_row:
                p_id = p_id_row["id"]
                cursor.execute("DELETE FROM attributes WHERE product_id = ?", (p_id,))
                cursor.execute("DELETE FROM agent_logs WHERE product_id = ?", (p_id,))
                cursor.execute("DELETE FROM conflicts WHERE product_id = ?", (p_id,))
            count += 1
            
    conn.commit()
    conn.close()
    
    return {"status": "success", "imported": count, "message": f"Successfully ingested batch of {count} products"}

@app.post("/api/settings")
def update_settings(settings: ConnectionSettings):
    SETTINGS["llm_provider"] = settings.llm_provider
    SETTINGS["gemini_api_key"] = settings.gemini_api_key
    SETTINGS["ollama_model"] = settings.ollama_model
    SETTINGS["llm_call_budget"] = max(0, settings.llm_call_budget)
    
    os.environ["LLM_PROVIDER"] = settings.llm_provider
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    os.environ["OLLAMA_MODEL"] = settings.ollama_model
    os.environ["LLM_CALL_BUDGET"] = str(SETTINGS["llm_call_budget"])
    
    save_settings(SETTINGS)
    return {"status": "success", "message": "Settings updated"}

@app.get("/api/settings")
def get_settings():
    return {
        "llm_provider": SETTINGS.get("llm_provider", "gemini"),
        "gemini_api_key": SETTINGS.get("gemini_api_key", ""),
        "ollama_model": SETTINGS.get("ollama_model", "llama3"),
        "llm_call_budget": SETTINGS.get("llm_call_budget", 50)
    }

@app.post("/api/profile")
async def profile_file(file: UploadFile = File(...)):
    contents = await file.read()
    from backend.ingestion.profiler import profile_dataset
    profile = profile_dataset(io.BytesIO(contents), filename=file.filename)
    return profile

@app.get("/api/llm-logs")
def get_llm_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    logs = cursor.execute("SELECT * FROM llm_calls ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(l) for l in logs]

@app.post("/api/evaluation")
def run_evaluation():
    format_path = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Expected Output - Delivery Format.csv"
    if not os.path.exists(format_path):
        raise HTTPException(status_code=404, detail="Expected format CSV file not found.")
        
    df_exp = pd.read_csv(format_path)
    total_rows = len(df_exp)
    if total_rows == 0:
        return {"status": "error", "message": "Evaluation file is empty"}
        
    conn = get_db_connection()
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM products")
    cursor.execute("DELETE FROM attributes")
    cursor.execute("DELETE FROM agent_logs")
    cursor.execute("DELETE FROM conflicts")
    conn.commit()
    
    now = datetime.now().isoformat()
    product_ids = []
    
    for _, row in df_exp.iterrows():
        mpn = str(row["Mfg_Part_Num"])
        desc = str(row["Part_Desc"])
        e1 = str(row.get("E1_Brand", ""))
        unilog = str(row.get("Unilog_Brand", ""))
        dib = str(row.get("DIB_Brand", ""))
        manuf = str(row.get("Part_Manuf", ""))
        
        cursor.execute(
            """INSERT INTO products 
            (mfg_part_num, part_desc, e1_brand, unilog_brand, dib_brand, part_manuf, status, created_at, updated_at) 
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (mpn, desc, e1, unilog, dib, manuf, now, now)
        )
        product_ids.append(cursor.lastrowid)
        
    conn.commit()
    conn.close()
    
    for pid in product_ids:
        run_pipeline_for_product(pid, api_key=SETTINGS.get("gemini_api_key"), llm_provider=SETTINGS.get("llm_provider"), ollama_model=SETTINGS.get("ollama_model"))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    accuracy_stats = {
        "classification": [],
        "manufacturer": [],
        "brand": [],
        "attributes": [],
        "uom": [],
        "descriptions": []
    }
    
    for idx, row in df_exp.iterrows():
        pid = product_ids[idx]
        p = cursor.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        attrs = cursor.execute("SELECT * FROM attributes WHERE product_id = ?", (pid,)).fetchall()
        
        expected_class = str(row.get("Classpath", "")).strip().lower()
        actual_class = str(p["classpath"] or "").strip().lower()
        accuracy_stats["classification"].append(1.0 if expected_class in actual_class or actual_class in expected_class else 0.0)
        
        expected_mfr = str(row.get("MANUFACTURER_NAME", "")).strip().lower()
        actual_mfr = str(p["part_manuf"] or "").strip().lower()
        accuracy_stats["manufacturer"].append(1.0 if expected_mfr in actual_mfr or actual_mfr in expected_mfr else 0.0)
        
        expected_brand = str(row.get("BRAND_NAME", "")).strip().lower()
        actual_brand = (p["e1_brand"] or p["unilog_brand"] or p["dib_brand"] or "").strip().lower()
        accuracy_stats["brand"].append(1.0 if expected_brand in actual_brand or actual_brand in expected_brand else 0.0)
        
        desc_matches = []
        for key, exp_key in [("invoice_desc", "INVOICE_DESC"), ("mobile_desc", "MOBILE_DESC"), ("short_desc", "SHORT_DESC"), ("long_desc", "LONG_DESC1")]:
            exp_val = str(row.get(exp_key, "")).strip().lower()
            act_val = str(p[key] or "").strip().lower()
            if exp_val and act_val:
                import difflib
                ratio = difflib.SequenceMatcher(None, exp_val, act_val).ratio()
                desc_matches.append(ratio)
            else:
                desc_matches.append(0.0)
        accuracy_stats["descriptions"].append(sum(desc_matches) / len(desc_matches) if desc_matches else 1.0)
        
        attr_lookup = {a["label"].lower(): a for a in attrs}
        attr_matches = []
        uom_matches = []
        for i in range(1, 10):
            exp_label = str(row.get(f"ATTRIBUTE_LABEL {i}", "")).strip().lower()
            exp_value = str(row.get(f"ATTRIBUTE_VALUE {i}", "")).strip().lower()
            exp_uom = str(row.get(f"ATTRIBUTE_UOM {i}", "")).strip().lower()
            
            if exp_label and exp_label != "nan":
                act_attr = attr_lookup.get(exp_label)
                if act_attr:
                    act_value = str(act_attr["value"]).strip().lower()
                    act_uom = str(act_attr["uom"] or "").strip().lower()
                    
                    attr_matches.append(1.0 if exp_value in act_value or act_value in exp_value else 0.0)
                    uom_matches.append(1.0 if exp_uom == act_uom else 0.0)
                else:
                    attr_matches.append(0.0)
                    uom_matches.append(0.0)
        if attr_matches:
            accuracy_stats["attributes"].append(sum(attr_matches) / len(attr_matches))
        if uom_matches:
            accuracy_stats["uom"].append(sum(uom_matches) / len(uom_matches))
            
    conn.close()
    
    metrics = {}
    for key, vals in accuracy_stats.items():
        metrics[key] = round((sum(vals) / len(vals)) * 100, 1) if vals else 100.0
        
    overall = round(sum(metrics.values()) / len(metrics), 1)
    metrics["overall"] = overall
    
    return {
        "status": "success",
        "processed_count": total_rows,
        "metrics": metrics
    }

@app.post("/api/test-connection")
def test_connection(settings: ConnectionSettings):
    provider = settings.llm_provider
    if provider == "gemini":
        if not settings.gemini_api_key:
            return {"status": "error", "message": "Gemini API Key is empty"}
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            # A lightweight prompt to test connection
            response = model.generate_content("hello")
            if response.text:
                return {"status": "success", "message": "Gemini API connection successful!"}
            else:
                return {"status": "error", "message": "Gemini API did not return text."}
        except Exception as e:
            return {"status": "error", "message": f"Gemini connection failed: {str(e)}"}
    elif provider == "ollama":
        import urllib.request
        import json
        model = settings.ollama_model or "llama3"
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                tags_data = json.loads(response.read().decode("utf-8"))
                models = [m["name"] for m in tags_data.get("models", [])]
                
                # Check if the specific model is downloaded
                found = False
                for m in models:
                    if model in m or m in model:
                        found = True
                        break
                
                if found:
                    return {"status": "success", "message": f"Ollama connection successful! Model '{model}' is installed."}
                else:
                    return {
                        "status": "warning", 
                        "message": f"Ollama is running, but model '{model}' was not found. Available models: {', '.join(models) or 'None'}"
                    }
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Could not connect to Ollama server at http://localhost:11434. Make sure 'ollama serve' is running. Error: {str(e)}"
            }
    return {"status": "error", "message": "Unknown provider"}

@app.get("/api/graph/{product_id}")
def get_product_graph(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    product = cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
        
    attributes = cursor.execute("SELECT * FROM attributes WHERE product_id = ?", (product_id,)).fetchall()
    conn.close()
    
    nodes = []
    links = []
    
    # Center node
    nodes.append({"id": "product", "label": product["mfg_part_num"], "type": "product", "val": 15})
    
    # Brand node
    if product["part_manuf"]:
        nodes.append({"id": "brand", "label": product["part_manuf"], "type": "brand", "val": 12})
        links.append({"source": "product", "target": "brand", "relation": "manufactured_by"})
        
    # Category node
    if product["category"]:
        nodes.append({"id": "category", "label": product["category"], "type": "category", "val": 12})
        links.append({"source": "product", "target": "category", "relation": "belongs_to"})
        
    # Standard Node (e.g. ISO/ANSI)
    nodes.append({"id": "standards", "label": "Industry Standards (ISO 15/ANSI)", "type": "standard", "val": 10})
    links.append({"source": "product", "target": "standards", "relation": "conforms_to"})
    
    # Attribute nodes
    for i, attr in enumerate(attributes):
        node_id = f"attr_{i}"
        label = f"{attr['label']}: {attr['value']}{' ' + attr['uom'] if attr['uom'] else ''}"
        nodes.append({"id": node_id, "label": label, "type": "attribute", "val": 8})
        links.append({"source": "product", "target": node_id, "relation": "has_attribute"})
        
    return {"nodes": nodes, "links": links}

@app.get("/api/export")
def export_enriched_csv():
    # Read the expected delivery format headers
    format_path = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Expected Output - Delivery Format.csv"
    if os.path.exists(format_path):
        with open(format_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
    else:
        # Fallback headers list
        headers = ["MFR URL", "PART_NUMBER", "Mfg_Part_Num", "Part_Desc", "Part_Manuf", "MANUFACTURER_NAME", "BRAND_NAME"]
        for i in range(1, 21):
            headers.append(f"ITEM_FEATURES_{i}")
        for i in range(1, 51):
            headers.extend([f"ATTRIBUTE_LABEL {i}", f"ATTRIBUTE_VALUE {i}", f"ATTRIBUTE_UOM {i}"])
            
    conn = get_db_connection()
    cursor = conn.cursor()
    
    products = cursor.execute("SELECT * FROM products WHERE status = 'completed'").fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    
    # Write rows
    for p in products:
        p_id = p["id"]
        attrs = cursor.execute("SELECT * FROM attributes WHERE product_id = ?", (p_id,)).fetchall()
        
        # Build attribute lookup mapping
        attr_vals = {}
        for idx, a in enumerate(attrs):
            i = idx + 1
            attr_vals[f"ATTRIBUTE_LABEL {i}"] = a["label"]
            attr_vals[f"ATTRIBUTE_VALUE {i}"] = a["value"]
            attr_vals[f"ATTRIBUTE_UOM {i}"] = a["uom"]
            
        # Build features list — map DB column 'label' to pipeline key 'attribute'
        from backend.pipeline import generate_item_features
        features = generate_item_features([{"attribute": a["label"], "value": a["value"], "uom": a["uom"]} for a in attrs])
        
        row = []
        for h in headers:
            if h == "MFR URL":
                row.append(p["mfr_url"] or "")
            elif h == "Ref URL 1":
                row.append(p["ref_url_1"] or "")
            elif h == "Ref URL 2":
                row.append(p["ref_url_2"] or "")
            elif h == "Ref URL 3":
                row.append(p["ref_url_3"] or "")
            elif h == "Ref URL 4":
                row.append(p["ref_url_4"] or "")
            elif h == "Ref URL 5":
                row.append(p["ref_url_5"] or "")
            elif h in ["PART_NUMBER", "Mfg_Part_Num", "MANUFACTURER_PART_NUMBER"]:
                row.append(p["mfg_part_num"])
            elif h == "Product Name":
                row.append(p["product_name"] or "")
            elif h == "Part_Desc":
                row.append(p["part_desc"])
            elif h == "INVOICE_DESC":
                row.append(p["invoice_desc"] or "")
            elif h == "MOBILE_DESC":
                row.append(p["mobile_desc"] or "")
            elif h == "SHORT_DESC":
                row.append(p["short_desc"] or "")
            elif h == "LONG_DESC1":
                row.append(p["long_desc"] or "")
            elif h == "RETAIL_DESC":
                row.append(p["retail_desc"] or "")
            elif h == "MARKETING_DESCRIPTION":
                row.append(p["marketing_description"] or "")
            elif h == "With":
                row.append(p["with_field"] or "")
            elif h == "Product Image":
                row.append(p["product_image"] or "")
            elif h in ["Specification Sheet", "Catalog"]:
                row.append(p["specification_sheet"] or "")
            elif h == "Classpath":
                row.append(p["classpath"] or "")
            elif h == "MANUFACTURER_NAME":
                row.append(p["resolved_manufacturer"] or "")
            elif h == "BRAND_NAME":
                row.append(p["resolved_brand"] or "")
            elif h == "Part_Manuf":
                row.append(p["part_manuf"] or "")
            elif h == "E1_Brand":
                row.append(p["e1_brand"] or "")
            elif h == "Unilog_Brand":
                row.append(p["unilog_brand"] or "")
            elif h == "DIB_Brand":
                row.append(p["dib_brand"] or "")
            elif h in attr_vals:
                row.append(attr_vals[h])
            elif h == "Actual Image (Yes/No)":
                row.append("Yes")
            elif h.startswith("ITEM_FEATURES_"):
                try:
                    f_idx = int(h.split("_")[-1]) - 1
                    row.append(features[f_idx] if f_idx < len(features) else "")
                except Exception:
                    row.append("")
            else:
                row.append("")
                
        writer.writerow(row)
        
    conn.close()
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=enriched_products.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
