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
    
    # Dynamically alter table to add columns in case the DB exists
    new_cols = [
        "resolved_manufacturer", "resolved_brand", "retail_desc", "marketing_description",
        "product_name", "with_field", "ref_url_1", "ref_url_2", "ref_url_3", "ref_url_4", "ref_url_5",
        "product_image", "specification_sheet"
    ]
    for col in new_cols:
        try:
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col} TEXT")
        except Exception:
            pass
    
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
        input_size INTEGER,
        output TEXT,
        confidence REAL,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
    """)
    
    # Create unique index on products.mfg_part_num to optimize uploads and queries
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_mfg_part_num ON products (mfg_part_num);")
    
    conn.commit()
    conn.close()
    print("Database initialized successfully at", DB_PATH)

if __name__ == "__main__":
    init_db()
