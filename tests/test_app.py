import pytest
import pandas as pd
from src.database import DatabaseManager
from src.collector import AptTradeCollector
from src.analytics import compute_kpis, filter_trades
from src.ai_analyst import GeminiAnalyst

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

def test_daily_detail_and_ai_summary_caching(tmp_path):
    db_path = tmp_path / "test_cache.db"
    db = DatabaseManager(db_path=db_path)
    db.init_db()
    
    # Insert sample trade for 2026-09-30
    sample = [{
        "id": "test_1",
        "deal_date": "2026-09-30",
        "deal_year": 2026,
        "deal_month": 9,
        "deal_day": 30,
        "sido": "서울특별시",
        "sigungu": "서초구",
        "sigungu_code": "11650",
        "umd_name": "반포동",
        "apt_name": "아크로리버파크",
        "exclusive_area": 84.9,
        "pyeong": 25.7,
        "pyeong_category": "중소형",
        "floor": 18,
        "build_year": 2016,
        "deal_amount": 420000,
        "pyeong_price": 16342.4,
        "is_cancel": 0,
        "cancel_date": "",
        "created_at": "2026-09-30 00:00:00"
    }]
    db.upsert_trades(sample)
    
    # 1. Fetch trades by date
    trades = db.get_trades_by_date("2026-09-30")
    assert len(trades) == 1
    assert trades.iloc[0]["apt_name"] == "아크로리버파크"
    
    # 2. Check summary cache (initially None)
    cached = db.get_daily_summary("2026-09-30")
    assert cached is None
    
    # 3. Generate and save summary
    analyst = GeminiAnalyst(api_key="")
    summary_text = analyst.generate_summary(trades, "2026-09-30")
    db.save_daily_summary("2026-09-30", summary_text, model_name="gemini-2.5-flash")
    
    # 4. Re-fetch summary (now cached!)
    cached_again = db.get_daily_summary("2026-09-30")
    assert cached_again is not None
    assert cached_again["summary_markdown"] == summary_text
    assert "아크로리버파크" in cached_again["summary_markdown"]
