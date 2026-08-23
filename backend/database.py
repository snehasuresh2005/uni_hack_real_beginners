import sqlite3
import os
import json
import queue
import threading
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

class DatabaseWriter:
    """Thread-safe serialized database writer thread to queue and batch all SQLite writes."""
    def __init__(self):
        self.task_queue = queue.Queue()
        self.thread = None
        self.running = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if not self.running:
                self.running = True
                self.thread = threading.Thread(target=self._drain_queue, name="DbWriterThread", daemon=True)
                self.thread.start()

    def stop(self):
        with self._lock:
            if self.running:
                self.running = False
                self.task_queue.put(None)
                if self.thread:
                    self.thread.join()

    def execute(self, func, *args, wait=False, **kwargs):
        """Submit a DB write operation.
        func must be a callable accepting 'cursor' as its first argument.
        If wait=True, blocks until write completes and returns or raises.
        """
        self.start()  # Lazy start on first write execution
        task = {
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "event": threading.Event() if wait else None,
            "result": None,
            "error": None
        }
        self.task_queue.put(task)
        if wait:
            task["event"].wait()
            if task["error"]:
                raise task["error"]
            return task["result"]

    def _drain_queue(self):
        conn = sqlite3.connect(DB_PATH, timeout=60.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        
        while self.running:
            task = self.task_queue.get()
            if task is None:
                break
                
            func = task["func"]
            args = task["args"]
            kwargs = task["kwargs"]
            
            success = False
            for attempt in range(5):
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    cursor = conn.cursor()
                    res = func(cursor, *args, **kwargs)
                    conn.commit()
                    task["result"] = res
                    success = True
                    break
                except sqlite3.OperationalError as e:
                    conn.rollback()
                    if "locked" in str(e) or "busy" in str(e):
                        time.sleep(0.05 * (2 ** attempt)) # Exponential backoff retry
                        continue
                    else:
                        task["error"] = e
                        break
                except Exception as e:
                    conn.rollback()
                    task["error"] = e
                    break
            
            if not success and not task["error"]:
                task["error"] = sqlite3.OperationalError("Database lock could not be resolved after multiple write retries")
                
            if task["event"]:
                task["event"].set()
                
        conn.close()

db_writer = DatabaseWriter()


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
        "difficulty_reasons": "TEXT", "ai_drafted": "INTEGER DEFAULT 0",
        "pending_verification": "INTEGER DEFAULT 0"
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
        input_size INTEGER, -- Deprecated, use prompt_token_count
        output TEXT,
        confidence REAL,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
    """)
    
    # AI Knowledge Cache table for learned resolution patterns & web references
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_knowledge_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_key TEXT UNIQUE,
        part_manuf TEXT,
        mfg_prefix TEXT,
        resolved_brand TEXT,
        resolved_manufacturer TEXT,
        classpath TEXT,
        web_urls TEXT,
        attributes_json TEXT,
        source TEXT,
        created_at TEXT
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_knowledge_cache_pattern ON ai_knowledge_cache (pattern_key);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_knowledge_cache_manuf ON ai_knowledge_cache (part_manuf);")

    conn.commit()
    conn.close()
    print("Database initialized successfully at", DB_PATH)

if __name__ == "__main__":
    init_db()
