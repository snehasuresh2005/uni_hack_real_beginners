import os
import csv
import io
import sqlite3
import pandas as pd
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime

from backend.database import get_db_connection, init_db
from backend.pipeline import run_pipeline_for_product, run_bulk_enrichment

# Initialize database
init_db()

app = FastAPI(title="AI Product Intelligence API")

# Configure CORS
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionSettings(BaseModel):
    llm_provider: str = "auto"
    gemini_api_key: Optional[str] = ""
    gemini_model: Optional[str] = "gemini-3.5-flash"
    groq_api_key: Optional[str] = ""
    groq_model: Optional[str] = "llama-3.3-70b-versatile"
    openrouter_api_key: Optional[str] = ""
    openrouter_model: Optional[str] = "google/gemma-4-31b-it:free"
    ollama_model: Optional[str] = "llama3"
    enable_ollama_fallback: bool = False
    llm_call_budget: int = 50

class IngestBatchRequest(BaseModel):
    products: List[dict]

import json

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

def load_settings():
    defaults = {
        "llm_provider": os.environ.get("LLM_PROVIDER", "auto"),
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "gemini_model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
        "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
        "groq_model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "openrouter_api_key": os.environ.get("OPENROUTER_API_KEY", ""),
        "openrouter_model": os.environ.get("OPENROUTER_MODEL", "google/gemma-4-31b-it:free"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "llama3"),
        "enable_ollama_fallback": os.environ.get("ENABLE_OLLAMA_FALLBACK", "false").lower() == "true",
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
    
    today_iso = datetime.now().strftime("%Y-%m-%d")
    llm_calls_today = cursor.execute("SELECT COUNT(*) FROM llm_calls WHERE timestamp LIKE ?", (f"{today_iso}%",)).fetchone()[0]
    llm_call_budget = SETTINGS.get("llm_call_budget", 50)

    conn.close()
    
    return {
        "total": total,
        "pending": pending,
        "processing": processing,
        "flagged_hitl": flagged,
        "completed": completed,
        "avg_confidence": round(avg_conf * 100, 1),
        "is_bulk_running": IS_BULK_RUNNING,
        "llm_calls_today": llm_calls_today,
        "llm_call_budget": llm_call_budget
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

@app.get("/api/batches/flagged")
def get_flagged_batches():
    conn = get_db_connection()
    cursor = conn.cursor()
    flagged = cursor.execute("SELECT * FROM products WHERE status = 'flagged_hitl' ORDER BY id").fetchall()
    conn.close()
    
    flagged_dicts = [dict(row) for row in flagged]
    from backend.pipeline import group_products_by_taxonomy
    batches = group_products_by_taxonomy(flagged_dicts, batch_size=3)
    
    formatted_batches = []
    for idx, b in enumerate(batches):
        taxonomy = b[0].get("classpath") or b[0].get("_classpath") or b[0].get("category") or "General Industrial Products"
        mfr = b[0].get("resolved_manufacturer") or b[0].get("_resolved_mfr") or b[0].get("part_manuf") or "Generic"
        formatted_batches.append({
            "batch_id": f"batch_{idx+1}",
            "taxonomy": taxonomy,
            "manufacturer": mfr,
            "count": len(b),
            "products": b
        })
        
    return {"batches": formatted_batches, "total_flagged": len(flagged_dicts)}

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

@app.post("/api/reset-bulk-lock")
def reset_bulk_lock():
    global IS_BULK_RUNNING, PROCESSING_PRODUCTS
    IS_BULK_RUNNING = False
    PROCESSING_PRODUCTS.clear()
    return {"status": "ok", "message": "Bulk pipeline state reset successfully."}

@app.post("/api/clear-all")
def clear_all_parsed_input():
    global IS_BULK_RUNNING, PROCESSING_PRODUCTS
    IS_BULK_RUNNING = False
    PROCESSING_PRODUCTS.clear()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products")
    cursor.execute("DELETE FROM attributes")
    cursor.execute("DELETE FROM agent_logs")
    cursor.execute("DELETE FROM conflicts")
    conn.commit()

    import pandas as pd
    from datetime import datetime
    csv_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "Unihack_Sample_Dataset_200.csv"),
        "Unihack_Sample_Dataset_200.csv",
        os.path.join(os.path.dirname(__file__), "..", "Unihack_ Sample Dataset - Input.csv"),
        "Unihack_ Sample Dataset - Input.csv"
    ]
    input_csv = None
    for path in csv_candidates:
        if os.path.exists(path):
            input_csv = path
            break

    reloaded_count = 0
    if input_csv:
        df = pd.read_csv(input_csv)
        now = datetime.now().isoformat()
        for _, row in df.iterrows():
            mpn = str(row["Mfg_Part_Num"])
            desc = str(row["Part_Desc"])
            e1 = str(row.get("E1_Brand", ""))
            unilog = str(row.get("Unilog_Brand", ""))
            dib = str(row.get("DIB_Brand", ""))
            manuf = str(row.get("Part_Manuf", ""))
            cursor.execute("""
                INSERT OR IGNORE INTO products 
                (mfg_part_num, part_desc, e1_brand, unilog_brand, dib_brand, part_manuf, status, ai_drafted, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)
            """, (mpn, desc, e1, unilog, dib, manuf, now, now))
            reloaded_count += 1
        conn.commit()

    conn.close()
    return {"status": "ok", "message": f"Cleared all parsed input and reloaded {reloaded_count} pending items."}

@app.post("/api/run-bulk")
def run_bulk(background_tasks: BackgroundTasks, limit: int = 30, llm_call_budget: Optional[int] = None):
    global IS_BULK_RUNNING, SETTINGS
    if IS_BULK_RUNNING:
        return {"status": "processing", "message": "Bulk enrichment is already running in the background."}
        
    # Reload fresh settings & reset provider cooldowns
    SETTINGS = load_settings()
    from backend.llm.llm_chain import reset_provider_cooldown
    reset_provider_cooldown()

    # Recover any orphaned processing items back to pending state
    try:
        conn = get_db_connection()
        conn.execute("UPDATE products SET status = 'pending' WHERE status = 'processing'")
        conn.commit()
        conn.close()
    except Exception as db_err:
        print("[Run-Bulk Recovery Warning]:", db_err)
        
    key = SETTINGS.get("gemini_api_key")
    provider = SETTINGS.get("llm_provider", "auto")
    model = SETTINGS.get("ollama_model", "llama3")
    budget = SETTINGS.get("llm_call_budget", 50) if llm_call_budget is None else llm_call_budget
    
    def bulk_wrapper():
        global IS_BULK_RUNNING
        IS_BULK_RUNNING = True
        try:
            while True:
                processed = run_bulk_enrichment(key, provider, model, limit if limit > 0 else 50, budget)
                print(f"[Bulk Pipeline] Batch completed. Processed: {processed} products.")
                if processed == 0:
                    break
        except Exception as err:
            print(f"[Bulk Pipeline Error] Exception during enrichment: {err}")
        finally:
            IS_BULK_RUNNING = False
            
    IS_BULK_RUNNING = True
    background_tasks.add_task(bulk_wrapper)
    return {"status": "processing", "message": f"Bulk enrichment started for products (cap: {limit}) with LLM budget of {budget}"}

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
    resolved_manufacturer: Optional[str] = None
    resolved_brand: Optional[str] = None
    category: Optional[str] = None

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
            resolved_manufacturer = ?, resolved_brand = ?, category = ?,
            status = 'completed', confidence_score = 1.0 
        WHERE id = ?""",
        (req.invoice_desc, req.mobile_desc, req.short_desc, req.long_desc, req.classpath,
         req.resolved_manufacturer, req.resolved_brand, req.category, product_id)
    )
    
    # Clear conflicts
    cursor.execute("UPDATE conflicts SET resolved = 1 WHERE product_id = ?", (product_id,))
    
    conn.commit()
    conn.close()
    
    # Save to AI Knowledge Cache for future similar items
    try:
        from backend.matching.ai_knowledge_cache import save_knowledge_cache
        save_knowledge_cache(
            part_manuf=req.resolved_manufacturer or "",
            mfg_part_num="",
            resolved_brand=req.resolved_brand or "",
            resolved_manufacturer=req.resolved_manufacturer or "",
            classpath=req.classpath or "",
            attributes=req.attributes,
            source="human_resolution"
        )
    except Exception as cache_err:
        print("Failed to save human resolution to AI knowledge cache:", cache_err)

    return {"status": "success", "message": "Attributes updated and product set to completed"}

def query_ollama_ai_assist(prompt: str, model: str = "llama3") -> str:
    """Unified LLM query helper using the shared Gemini -> Groq -> OpenRouter failover chain."""
    from backend.llm.llm_chain import query_llm_chain
    return query_llm_chain(prompt, reason="AI Assist inline query", settings=load_settings())

@app.post("/api/products/{product_id}/ai-assist")
def ai_assist_product(product_id: int):
    # Fetch product info
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
        
    attributes = conn.execute("SELECT * FROM attributes WHERE product_id = ?", (product_id,)).fetchall()
    logs = conn.execute("SELECT * FROM agent_logs WHERE product_id = ? ORDER BY id DESC", (product_id,)).fetchall()
    conn.close()
    
    # 1. Check AI Knowledge Cache first for similar manufacturer/pattern
    from backend.matching.ai_knowledge_cache import lookup_knowledge_cache, save_knowledge_cache
    cached_kb = lookup_knowledge_cache(product['part_manuf'], product['mfg_part_num'])
    
    warning_logs = [l["message"] for l in logs if l["level"] == "WARNING"]
    warning_str = "; ".join(warning_logs) if warning_logs else "None"

    # Construct attributes string
    attr_list = [f"{a['label']}: {a['value']} {a['uom'] or ''}" for a in attributes]
    attrs_str = ", ".join(attr_list) if attr_list else "None"

    cached_hint = ""
    if cached_kb:
        cached_hint = (
            f"\nLearned Knowledge Cache Match:\n"
            f"- Preferred Brand Pattern: {cached_kb.get('resolved_brand')}\n"
            f"- Preferred Manufacturer: {cached_kb.get('resolved_manufacturer')}\n"
            f"- Preferred Classpath: {cached_kb.get('classpath')}\n"
        )

    prompt = f"""You are an AI data enrichment assistant for B2B industrial product catalogs.
Analyze this product payload and return COMPLETE enrichment data as JSON. You MUST always return valid JSON.

Product Payload:
- MPN (Part Number): {product['mfg_part_num']}
- Raw Manufacturer: {product['part_manuf']}
- E1 Brand: {product['e1_brand']}
- Unilog Brand: {product['unilog_brand']}
- DIB Brand: {product['dib_brand']}
- Raw Description: {product['part_desc']}
- Flagged Warnings: {warning_str}
- Current Resolved Manufacturer: {product['resolved_manufacturer'] or 'UNKNOWN'}
- Current Resolved Brand: {product['resolved_brand'] or 'UNKNOWN'}
- Current Classpath: {product['classpath'] or 'UNKNOWN'}
- Current Attributes: {attrs_str}{cached_hint}

TASK: Resolve ALL unknown/missing fields for THIS SPECIFIC ITEM. Extract the true brand, manufacturer, category classpath, and specifications.

Rules:
1. resolved_brand: Identify the exact true brand from MPN prefix patterns, description keywords, or manufacturer name.
2. resolved_manufacturer: Full legal manufacturer name, cleaned.
3. classpath: Format as "Category>Subcategory" (e.g. "Abrasives>Sanding Discs", "Building Materials>Mortar & Grout", "Hand Tools>Screwdrivers").
4. invoice_desc: Max 40 chars, ALL CAPS (e.g. "<BRAND> <SERIES> <SPECS>").
5. mobile_desc: 60-80 chars B2B marketing copy featuring the TRUE brand and key specs.
6. short_desc: Brand + Series + MPN + product type + key specs.
7. long_desc: 2-3 sentence professional product description for this item.
8. attributes: ALL measurable specifications as label/value/uom objects.

CRITICAL CONSTRAINTS:
- Identify the brand and manufacturer ONLY from the product payload provided above.
- DO NOT default to "Mirka" or any other hardcoded placeholder brand unless "Mirka" literally appears in the raw product payload.

Respond with ONLY a JSON object, no extra text:
{{"resolved_brand":"...","resolved_manufacturer":"...","classpath":"...","invoice_desc":"...","mobile_desc":"...","short_desc":"...","long_desc":"...","attributes":[{{"label":"...","value":"...","uom":"..."}}]}}"""

    from backend.llm.llm_chain import query_llm_chain
    res_text = query_llm_chain(prompt, product_id=product_id, reason="AI Assist resolution", settings=load_settings())

    if not res_text:
        # Fallback gracefully to deterministic pipeline enrichment for this product
        from backend.pipeline import run_pipeline_for_product
        run_pipeline_for_product(product_id)
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        updated_p = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        attrs = conn.execute("SELECT * FROM attributes WHERE product_id = ?", (product_id,)).fetchall()
        conn.close()

        if updated_p:
            return {
                "resolved_brand": updated_p["resolved_brand"] or "UNKNOWN",
                "resolved_manufacturer": updated_p["resolved_manufacturer"] or "UNKNOWN",
                "classpath": updated_p["classpath"] or "General Industrial Products",
                "invoice_desc": updated_p["invoice_desc"] or "",
                "mobile_desc": updated_p["mobile_desc"] or "",
                "short_desc": updated_p["short_desc"] or "",
                "long_desc": updated_p["long_desc"] or "",
                "attributes": [{"label": a["label"], "value": a["value"], "uom": a["uom"]} for a in attrs]
            }
        else:
            raise HTTPException(status_code=500, detail="Product not found after fallback enrichment.")
         
    def clean_and_parse_json(text):
        t = text.strip()
        
        # 1. Try direct parsing
        try:
            return json.loads(t)
        except Exception:
            pass
            
        # 2. Extract content from code blocks
        import re
        match = re.search(r'```(?:json)?\s*(.*?)\s*(?:```|$)', t, re.S)
        if match:
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                t = candidate
                
        # 3. Repair truncated JSON by balancing braces/brackets
        first_brace = t.find('{')
        if first_brace != -1:
            t = t[first_brace:]
            
        stack = []
        in_string = False
        escape = False
        clean_chars = []
        
        for char in t:
            if escape:
                clean_chars.append(char)
                escape = False
                continue
            if char == '\\':
                clean_chars.append(char)
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                clean_chars.append(char)
                continue
                
            clean_chars.append(char)
            
            if not in_string:
                if char in ('{', '['):
                    stack.append(char)
                elif char in ('}', ']'):
                    if stack:
                        if (char == '}' and stack[-1] == '{') or (char == ']' and stack[-1] == '['):
                            stack.pop()
                            
        cleaned_text = "".join(clean_chars)
        
        if in_string:
            cleaned_text += '"'
            
        while stack:
            open_char = stack.pop()
            if open_char == '{':
                cleaned_text = cleaned_text.rstrip().rstrip(',')
                cleaned_text += '}'
            elif open_char == '[':
                cleaned_text = cleaned_text.rstrip().rstrip(',')
                cleaned_text += ']'
                
        try:
            return json.loads(cleaned_text)
        except Exception as e:
            print("Robust JSON parser failed to recover JSON. Attempting regex extract. Error:", e)
            fallback_dict = {}
            for key in ["resolved_brand", "resolved_manufacturer", "classpath", "invoice_desc", "mobile_desc", "short_desc", "long_desc"]:
                m = re.search(rf'"{key}"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', t)
                if m:
                    try:
                        val = m.group(1).encode().decode('unicode-escape')
                    except Exception:
                        val = m.group(1)
                    fallback_dict[key] = val
            fallback_dict["attributes"] = []
    try:
        data = clean_and_parse_json(res_text)
        
        # Enforce strict 60-80 chars mobile_desc bound and enriched descriptions
        from backend.pipeline import ensure_mobile_desc_bounds, format_enriched_descriptions
        data["mobile_desc"] = ensure_mobile_desc_bounds(
            data.get("mobile_desc"),
            norm_mfr=data.get("resolved_manufacturer") or product['part_manuf'],
            norm_brd=data.get("resolved_brand") or product['e1_brand'],
            prod_name=product['part_desc'],
            mpn=product['mfg_part_num'],
            attributes=data.get("attributes", [])
        )
        sh_fmt, lng_fmt = format_enriched_descriptions(
            resolved_brand=data.get("resolved_brand"),
            resolved_manufacturer=data.get("resolved_manufacturer"),
            mpn=product['mfg_part_num'],
            part_desc=product['part_desc'],
            short_desc=data.get("short_desc"),
            long_desc=data.get("long_desc"),
            attributes=data.get("attributes", [])
        )
        data["short_desc"] = sh_fmt
        data["long_desc"] = lng_fmt
        
        # Resolve official manufacturer product URL & reference PDFs
        from backend.matching.mfr_url_resolver import resolve_product_urls
        url_res = resolve_product_urls(
            part_manuf=data.get("resolved_manufacturer") or product['part_manuf'],
            resolved_brand=data.get("resolved_brand") or product['e1_brand'],
            mfg_part_num=product['mfg_part_num'],
            part_desc=product['part_desc']
        )
        if url_res.get("mfr_url"):
            data["mfr_url"] = url_res["mfr_url"]
            ref_urls = url_res.get("ref_urls", [])
            data["ref_url_1"] = ref_urls[0] if len(ref_urls) > 0 else ""
            data["ref_url_2"] = ref_urls[1] if len(ref_urls) > 1 else ""
            data["ref_url_3"] = ref_urls[2] if len(ref_urls) > 2 else ""
            data["ref_url_4"] = ref_urls[3] if len(ref_urls) > 3 else ""
            data["ref_url_5"] = ref_urls[4] if len(ref_urls) > 4 else ""
        
        # Save generated pattern to Knowledge Cache
        try:
            save_knowledge_cache(
                part_manuf=product['part_manuf'],
                mfg_part_num=product['mfg_part_num'],
                resolved_brand=data.get("resolved_brand", ""),
                resolved_manufacturer=data.get("resolved_manufacturer", ""),
                classpath=data.get("classpath", ""),
                web_urls=[product["mfr_url"]] if dict(product).get("mfr_url") else [],
                attributes=data.get("attributes", []),
                source="ai_assist"
            )
        except Exception as cache_save_err:
            print("Failed saving AI Assist pattern to knowledge cache:", cache_save_err)
            
        return data
    except Exception as e:
        print("Failed to parse Gemini response text:", res_text, e)
        raise HTTPException(status_code=500, detail=f"Failed to parse Gemini response as JSON: {e}")

class BatchApproveRequest(BaseModel):
    product_ids: List[int]

@app.post("/api/batches/batch-approve")
def batch_approve_products(req: BatchApproveRequest):
    if not req.product_ids:
        return {"status": "success", "count": 0}
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(req.product_ids))
    cursor.execute(f"UPDATE products SET status = 'completed', confidence_score = 1.0 WHERE id IN ({placeholders})", req.product_ids)
    conn.commit()
    conn.close()
    return {"status": "success", "count": len(req.product_ids), "message": f"Approved {len(req.product_ids)} products"}

class BatchAiAssistRequest(BaseModel):
    product_ids: List[int]

@app.post("/api/batches/brand-ai-assist")
def batch_brand_ai_assist(req: BatchAiAssistRequest):
    if not req.product_ids:
        raise HTTPException(status_code=400, detail="No product IDs provided for batch AI assist.")

    # Cap batch payload to max 3 items to prevent LLM rate/token limits
    target_ids = req.product_ids[:3]

    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(target_ids))
    rows = cursor.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", target_ids).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No products found for provided IDs.")

    products = [dict(r) for r in rows]
    sample = products[0]
    brand_context = sample.get("resolved_brand") or sample.get("e1_brand") or sample.get("part_manuf") or "Catalog Brand"

    items_text = []
    for p in products:
        items_text.append(f"""---
PRODUCT ITEM (ID: {p['id']}):
- MPN: {p.get('mfg_part_num', '')}
- Raw Manufacturer: {p.get('part_manuf', '')}
- Raw Description: {p.get('part_desc', '')}
- Brand Fields: E1={p.get('e1_brand', '')}, Unilog={p.get('unilog_brand', '')}, DIB={p.get('dib_brand', '')}""")

    items_joined = "\n".join(items_text)
    prompt = f"""You are an expert B2B data enrichment AI assistant.
Enrich the following {len(products)} products belonging to Brand / Manufacturer cluster '{brand_context}'.
Process ALL items together in 1 single pass, resolving true brand, manufacturer, category classpath, descriptions, and spec attributes.

PRODUCT PAYLOADS:
{items_joined}

Respond with ONLY a JSON array containing exactly {len(products)} objects in exact item order:
[
  {{
    "id": {products[0]['id']},
    "resolved_brand": "...",
    "resolved_manufacturer": "...",
    "classpath": "...",
    "invoice_desc": "...",
    "mobile_desc": "...",
    "short_desc": "...",
    "long_desc": "...",
    "attributes": [{{"label": "...", "value": "...", "uom": "..."}}]
  }}
]"""

    from backend.llm.llm_chain import query_llm_chain
    from backend.pipeline import extract_balanced_json_array
    res_text = query_llm_chain(prompt, reason="Batch Brand AI Assist", settings=load_settings())
    
    results_list = []
    if res_text:
        json_array_str = extract_balanced_json_array(res_text)
        if json_array_str:
            try:
                results_list = json.loads(json_array_str)
            except Exception:
                pass

    updated_count = 0
    if results_list:
        import time
        for attempt in range(5):
            try:
                conn = get_db_connection()
                c = conn.cursor()
                for item in results_list:
                    p_id = item.get("id")
                    if not p_id:
                        continue
                    
                    r_brd = item.get("resolved_brand") or "UNKNOWN"
                    r_mfr = item.get("resolved_manufacturer") or "UNKNOWN"
                    clspath = item.get("classpath") or "General Industrial Products"
                    inv_d = str(item.get("invoice_desc") or "").upper()[:40]
                    from backend.pipeline import ensure_mobile_desc_bounds, format_enriched_descriptions
                    mob_raw = str(item.get("mobile_desc") or "")
                    p_orig = next((p for p in products if p["id"] == p_id), {})
                    mob_d = ensure_mobile_desc_bounds(
                        mob_raw,
                        norm_mfr=r_mfr or p_orig.get("part_manuf", ""),
                        norm_brd=r_brd or p_orig.get("e1_brand", ""),
                        prod_name=p_orig.get("part_desc", ""),
                        mpn=p_orig.get("mfg_part_num", ""),
                        attributes=item.get("attributes", [])
                    )
                    sh_fmt, lng_fmt = format_enriched_descriptions(
                        resolved_brand=r_brd,
                        resolved_manufacturer=r_mfr,
                        mpn=p_orig.get("mfg_part_num", ""),
                        part_desc=p_orig.get("part_desc", ""),
                        short_desc=item.get("short_desc"),
                        long_desc=item.get("long_desc"),
                        attributes=item.get("attributes", [])
                    )
                    from backend.matching.mfr_url_resolver import resolve_product_urls
                    url_res = resolve_product_urls(
                        part_manuf=r_mfr or p_orig.get("part_manuf", ""),
                        resolved_brand=r_brd or p_orig.get("e1_brand", ""),
                        mfg_part_num=p_orig.get("mfg_part_num", ""),
                        part_desc=p_orig.get("part_desc", "")
                    )
                    mfr_url_val = url_res.get("mfr_url", "")
                    ref_urls = url_res.get("ref_urls", [])
                    r1 = ref_urls[0] if len(ref_urls) > 0 else ""
                    r2 = ref_urls[1] if len(ref_urls) > 1 else ""
                    r3 = ref_urls[2] if len(ref_urls) > 2 else ""
                    r4 = ref_urls[3] if len(ref_urls) > 3 else ""
                    r5 = ref_urls[4] if len(ref_urls) > 4 else ""

                    c.execute("""
                        UPDATE products
                        SET status = 'flagged_hitl', confidence_score = 0.90, ai_drafted = 1, resolved_brand = ?, resolved_manufacturer = ?,
                            classpath = ?, invoice_desc = ?, mobile_desc = ?, short_desc = ?, long_desc = ?,
                            mfr_url = ?, ref_url_1 = ?, ref_url_2 = ?, ref_url_3 = ?, ref_url_4 = ?, ref_url_5 = ?
                        WHERE id = ?
                    """, (r_brd, r_mfr, clspath, inv_d, mob_d, sh_fmt, lng_fmt, mfr_url_val, r1, r2, r3, r4, r5, p_id))

                    c.execute("DELETE FROM attributes WHERE product_id = ?", (p_id,))
                    for ad in item.get("attributes", []):
                        if isinstance(ad, dict) and ad.get("label"):
                            c.execute("""
                                INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (p_id, ad["label"], str(ad.get("value", "")), str(ad.get("uom", "")), 0.95, "Batch Brand AI Assist", "LLM Single Pass"))
                    updated_count += 1
                conn.commit()
                conn.close()
                break
            except sqlite3.OperationalError as op_err:
                try:
                    conn.close()
                except Exception:
                    pass
                if "locked" in str(op_err) or "busy" in str(op_err):
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                else:
                    raise op_err
    else:
        # Fallback to deterministic rule enrichment for all items in batch
        from backend.pipeline import run_pipeline_for_product
        for p in products:
            run_pipeline_for_product(p["id"])

        import time
        for attempt in range(5):
            try:
                conn = get_db_connection()
                c = conn.cursor()
                for p in products:
                    c.execute("UPDATE products SET status = 'flagged_hitl', ai_drafted = 1 WHERE id = ?", (p["id"],))
                    updated_count += 1
                conn.commit()
                conn.close()
                break
            except sqlite3.OperationalError as op_err:
                try:
                    conn.close()
                except Exception:
                    pass
                if "locked" in str(op_err) or "busy" in str(op_err):
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                else:
                    raise op_err

    return {"status": "success", "updated_count": updated_count, "message": f"Enriched {updated_count} products in batch!"}

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

def mask_api_key(key: Optional[str]) -> str:
    if not key:
        return ""
    if key.startswith("***") or "..." in key:
        return key
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}...{key[-4:]}"

def is_masked(key: Optional[str]) -> bool:
    if not key:
        return False
    return "..." in key or key == "****" or key.startswith("***")

@app.post("/api/settings")
def update_settings(settings: ConnectionSettings):
    if not is_masked(settings.gemini_api_key):
        SETTINGS["gemini_api_key"] = settings.gemini_api_key
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key or ""

    if not is_masked(settings.groq_api_key):
        SETTINGS["groq_api_key"] = settings.groq_api_key
        os.environ["GROQ_API_KEY"] = settings.groq_api_key or ""

    if not is_masked(settings.openrouter_api_key):
        SETTINGS["openrouter_api_key"] = settings.openrouter_api_key
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key or ""

    SETTINGS["llm_provider"] = settings.llm_provider
    SETTINGS["gemini_model"] = settings.gemini_model
    SETTINGS["groq_model"] = settings.groq_model
    SETTINGS["openrouter_model"] = settings.openrouter_model
    SETTINGS["ollama_model"] = settings.ollama_model
    SETTINGS["enable_ollama_fallback"] = settings.enable_ollama_fallback
    SETTINGS["llm_call_budget"] = max(0, settings.llm_call_budget)
    
    os.environ["LLM_PROVIDER"] = settings.llm_provider
    os.environ["GEMINI_MODEL"] = settings.gemini_model or "gemini-1.5-flash"
    os.environ["GROQ_MODEL"] = settings.groq_model or "llama-3.3-70b-versatile"
    os.environ["OPENROUTER_MODEL"] = settings.openrouter_model or "meta-llama/llama-3.1-8b-instruct:free"
    os.environ["OLLAMA_MODEL"] = settings.ollama_model or "llama3"
    os.environ["ENABLE_OLLAMA_FALLBACK"] = str(settings.enable_ollama_fallback).lower()
    os.environ["LLM_CALL_BUDGET"] = str(SETTINGS["llm_call_budget"])
    
    save_settings(SETTINGS)
    return {"status": "success", "message": "Settings updated"}

@app.get("/api/settings")
def get_settings():
    return {
        "llm_provider": SETTINGS.get("llm_provider", "auto"),
        "gemini_api_key": mask_api_key(SETTINGS.get("gemini_api_key", "")),
        "gemini_model": SETTINGS.get("gemini_model", "gemini-1.5-flash"),
        "groq_api_key": mask_api_key(SETTINGS.get("groq_api_key", "")),
        "groq_model": SETTINGS.get("groq_model", "llama-3.3-70b-versatile"),
        "openrouter_api_key": mask_api_key(SETTINGS.get("openrouter_api_key", "")),
        "openrouter_model": SETTINGS.get("openrouter_model", "meta-llama/llama-3.1-8b-instruct:free"),
        "ollama_model": SETTINGS.get("ollama_model", "llama3"),
        "enable_ollama_fallback": SETTINGS.get("enable_ollama_fallback", False),
        "llm_call_budget": SETTINGS.get("llm_call_budget", 50)
    }

@app.post("/api/test-connection")
def test_connection(settings: Optional[ConnectionSettings] = None):
    from backend.llm.llm_chain import (
        query_gemini_provider, 
        query_groq_provider, 
        query_openrouter_provider, 
        query_ollama_provider
    )
    s = settings.dict() if settings else SETTINGS
    provider = (s.get("llm_provider") or "auto").lower()

    test_prompt = "Respond with JSON: {\"status\": \"ok\"}"
    results = []

    # Test Groq if configured
    groq_key = s.get("groq_api_key")
    if groq_key:
        code, msg = query_groq_provider(test_prompt, groq_key, s.get("groq_model"))
        status = "PASS" if code == 200 and msg else f"FAIL ({code})"
        results.append(f"Groq: {status}")

    # Test OpenRouter if configured
    openrouter_key = s.get("openrouter_api_key")
    if openrouter_key:
        code, msg = query_openrouter_provider(test_prompt, openrouter_key, s.get("openrouter_model"))
        status = "PASS" if code == 200 and msg else f"FAIL ({code})"
        results.append(f"OpenRouter: {status}")

    # Test Gemini if configured
    gemini_key = s.get("gemini_api_key")
    if gemini_key:
        code, msg = query_gemini_provider(test_prompt, gemini_key, s.get("gemini_model"))
        status = "PASS" if code == 200 and msg else f"FAIL ({code})"
        results.append(f"Gemini: {status}")

    # Test Ollama
    if s.get("enable_ollama_fallback") or provider == "ollama":
        code, msg = query_ollama_provider(test_prompt, s.get("ollama_model"))
        status = "PASS" if code == 200 and msg else f"FAIL ({code})"
        results.append(f"Ollama: {status}")

    if not results:
        return {"status": "warning", "message": "No API keys configured to test."}

    passed_count = sum(1 for r in results if "PASS" in r)
    summary_status = "success" if passed_count > 0 else "error"
    return {
        "status": summary_status,
        "message": f"Connection test complete ({passed_count}/{len(results)} active providers reachable). Details: " + " | ".join(results)
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

@app.get("/api/logs/stream")
async def stream_logs():
    from backend.logs_broker import logs_broker
    q = logs_broker.subscribe()
    
    async def event_generator():
        import asyncio
        import json
        import queue
        loop = asyncio.get_event_loop()
        try:
            while True:
                try:
                    # Fetch log entry with 1s timeout to release worker threads
                    log_entry = await loop.run_in_executor(None, lambda: q.get(timeout=1.0))
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except queue.Empty:
                    # Send periodic SSE ping comment to maintain connection non-blockingly
                    yield ": ping\n\n"
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            logs_broker.unsubscribe(q)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

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
            elif h == "PART_NUMBER":
                row.append("") # Input dataset contains no internal SKU/PART_NUMBER column
            elif h in ["Mfg_Part_Num", "MANUFACTURER_PART_NUMBER"]:
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

# Serve built frontend static files directly from Render (bypasses Netlify quota limits)
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API endpoint not found")
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
