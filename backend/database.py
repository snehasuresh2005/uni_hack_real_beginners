import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mfg_part_num TEXT,
        part_desc TEXT,
        e1_brand TEXT,
        unilog_brand TEXT,
        dib_brand TEXT,
        part_manuf TEXT,
        resolved_manufacturer TEXT,
        resolved_brand TEXT,
        status TEXT DEFAULT 'pending',
        confidence_score REAL DEFAULT 0.0,
        category TEXT,
        mfr_url TEXT,
        invoice_desc TEXT,
        mobile_desc TEXT,
        short_desc TEXT,
        long_desc TEXT,
        classpath TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    
    # One-time, idempotent migration for databases created by earlier versions.
    # Keeping migrations here prevents per-product ALTER TABLE calls and lock contention.
    product_columns = {
        "resolved_manufacturer": "TEXT", "resolved_brand": "TEXT", "retail_desc": "TEXT",
        "marketing_description": "TEXT", "product_name": "TEXT", "with_field": "TEXT",
        "ref_url_1": "TEXT", "ref_url_2": "TEXT", "ref_url_3": "TEXT", "ref_url_4": "TEXT",
        "ref_url_5": "TEXT", "product_image": "TEXT", "specification_sheet": "TEXT",
        "fingerprint": "TEXT", "difficulty_level": "TEXT", "difficulty_score": "REAL",
        "difficulty_reasons": "TEXT",
    }
    existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(products)")}
    for col, column_type in product_columns.items():
        if col not in existing_columns:
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col} {column_type}")
    
    # Attributes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attributes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        label TEXT,
        value TEXT,
        uom TEXT,
        confidence REAL,
        source TEXT,
        citation TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
    """)
    
    # Agent logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        agent_name TEXT,
        timestamp TEXT,
        message TEXT,
        level TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
    """)
    
    # Conflicts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conflicts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        field_name TEXT,
        agent_a TEXT,
        value_a TEXT,
        agent_b TEXT,
        value_b TEXT,
        resolved INTEGER DEFAULT 0,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
    """)
    
    # LLM calls logging table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS llm_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        reason_for_llm_call TEXT,
        model TEXT,
        timestamp TEXT,
        input_size INTEGER, # Deprecated, use prompt_token_count
        output TEXT,
        confidence REAL,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
    """)
    
    # Indexes used by upload, enrichment, and dashboard queries.
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_mfg_part_num ON products (mfg_part_num);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_status ON products (status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_fingerprint ON products (fingerprint, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attributes_product_id ON attributes (product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_logs_product_id ON agent_logs (product_id, id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_product_id ON conflicts (product_id, resolved);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_timestamp ON llm_calls (timestamp);")

    # Audit data is useful, but unbounded prompt/response and event retention is not.
    retention_days = int(os.environ.get("AUDIT_LOG_RETENTION_DAYS", "30"))
    if retention_days >= 0:
        cutoff = datetime.now().timestamp() - (retention_days * 86400)
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()
        cursor.execute("DELETE FROM agent_logs WHERE timestamp < ?", (cutoff_iso,))
        cursor.execute("DELETE FROM llm_calls WHERE timestamp < ?", (cutoff_iso,))
    
    conn.commit()
    conn.close()
    print("Database initialized successfully at", DB_PATH)

if __name__ == "__main__":
    init_db()
