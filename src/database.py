import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
try:
    from src.config import Config
except ImportError:
    from .config import Config

class DatabaseManager:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else Config.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize SQLite database with required tables and indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS apt_trades (
                id TEXT PRIMARY KEY,
                deal_date TEXT NOT NULL,
                deal_year INTEGER NOT NULL,
                deal_month INTEGER NOT NULL,
                deal_day INTEGER NOT NULL,
                sido TEXT NOT NULL,
                sigungu TEXT NOT NULL,
                sigungu_code TEXT NOT NULL,
                umd_name TEXT,
                apt_name TEXT NOT NULL,
                exclusive_area REAL NOT NULL,
                pyeong REAL NOT NULL,
                pyeong_category TEXT NOT NULL,
                floor INTEGER,
                build_year INTEGER,
                deal_amount INTEGER NOT NULL,
                pyeong_price REAL NOT NULL,
                is_cancel INTEGER DEFAULT 0,
                cancel_date TEXT,
                created_at TEXT NOT NULL
            )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deal_date ON apt_trades(deal_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sido_sigungu ON apt_trades(sido, sigungu)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_apt_name ON apt_trades(apt_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sigungu_code ON apt_trades(sigungu_code)")
            conn.commit()

    def upsert_trades(self, trades: list[dict]) -> int:
        """Insert or replace trade records into SQLite database."""
        if not trades:
            return 0
        
        self.init_db()
        inserted_count = 0
        
        sql = """
        INSERT INTO apt_trades (
            id, deal_date, deal_year, deal_month, deal_day,
            sido, sigungu, sigungu_code, umd_name, apt_name,
            exclusive_area, pyeong, pyeong_category, floor, build_year,
            deal_amount, pyeong_price, is_cancel, cancel_date, created_at
        ) VALUES (
            :id, :deal_date, :deal_year, :deal_month, :deal_day,
            :sido, :sigungu, :sigungu_code, :umd_name, :apt_name,
            :exclusive_area, :pyeong, :pyeong_category, :floor, :build_year,
            :deal_amount, :pyeong_price, :is_cancel, :cancel_date, :created_at
        )
        ON CONFLICT(id) DO UPDATE SET
            deal_amount = excluded.deal_amount,
            pyeong_price = excluded.pyeong_price,
            is_cancel = excluded.is_cancel,
            cancel_date = excluded.cancel_date,
            created_at = excluded.created_at
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, trades)
            inserted_count = cursor.rowcount
            conn.commit()
            
        return inserted_count

    def get_recent_trades(self, days: int = 7, exclude_canceled: bool = True) -> pd.DataFrame:
        """Retrieve trades within the specified recent days."""
        self.init_db()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        query = "SELECT * FROM apt_trades WHERE deal_date >= ?"
        params: list[object] = [cutoff_date]
        
        if exclude_canceled:
            query += " AND is_cancel = 0"
            
        query += " ORDER BY deal_date DESC, deal_amount DESC"
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            
        return df

    def get_all_trades(self, exclude_canceled: bool = True) -> pd.DataFrame:
        """Retrieve all trades stored in database."""
        self.init_db()
        query = "SELECT * FROM apt_trades"
        if exclude_canceled:
            query += " WHERE is_cancel = 0"
        query += " ORDER BY deal_date DESC, deal_amount DESC"
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn)
            
        return df

    def get_total_count(self) -> int:
        """Get total trade records count in database."""
        self.init_db()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM apt_trades")
            row = cursor.fetchone()
            return row[0] if row else 0
