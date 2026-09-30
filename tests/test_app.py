import pytest
import pandas as pd
from src.database import DatabaseManager
from src.collector import AptTradeCollector
from src.analytics import compute_kpis, filter_trades

def test_dashboard_data_loading(tmp_path):
    db_path = tmp_path / "test_app.db"
    db = DatabaseManager(db_path=db_path)
    db.init_db()
    
    collector = AptTradeCollector(api_key="", db_manager=db)
    saved = collector.collect_and_save(days=7, use_mock=True, count=30)
    assert saved == 30
    
    df_all = db.get_recent_trades(days=7, exclude_canceled=False)
    assert not df_all.empty
    assert len(df_all) == 30
    
    df_valid = db.get_recent_trades(days=7, exclude_canceled=True)
    assert not df_valid.empty
    
    kpi = compute_kpis(df_valid)
    assert kpi["total_deals"] == len(df_valid)
    assert kpi["avg_amount"] > 0
    assert kpi["avg_pyeong_price"] > 0
    
    filtered = filter_trades(df_all, {"exclude_cancel": True})
    assert len(filtered) == len(df_valid)
