import pytest
from pathlib import Path
from src.database import DatabaseManager

def test_db_init_and_upsert(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path=db_path)
    db.init_db()
    
    sample = [{
        "id": "11680_20260928_개포래미안_12_84.9",
        "deal_date": "2026-09-28",
        "deal_year": 2026,
        "deal_month": 9,
        "deal_day": 28,
        "sido": "서울특별시",
        "sigungu": "강남구",
        "sigungu_code": "11680",
        "umd_name": "개포동",
        "apt_name": "개포래미안",
        "exclusive_area": 84.9,
        "pyeong": 25.7,
        "pyeong_category": "중소형",
        "floor": 12,
        "build_year": 2020,
        "deal_amount": 250000,
        "pyeong_price": 9727.6,
        "is_cancel": 0,
        "cancel_date": "",
        "created_at": "2026-09-30 00:00:00"
    }]
    
    inserted = db.upsert_trades(sample)
    assert inserted == 1
    assert db.get_total_count() == 1
    
    # Duplicate insert test (Upsert should keep count = 1)
    inserted_again = db.upsert_trades(sample)
    assert db.get_total_count() == 1

def test_db_get_recent_trades_filtering(tmp_path):
    db_path = tmp_path / "test2.db"
    db = DatabaseManager(db_path=db_path)
    db.init_db()
    
    samples = [
        {
            "id": "1",
            "deal_date": "2026-09-28",
            "deal_year": 2026,
            "deal_month": 9,
            "deal_day": 28,
            "sido": "서울특별시",
            "sigungu": "강남구",
            "sigungu_code": "11680",
            "umd_name": "개포동",
            "apt_name": "단지A",
            "exclusive_area": 84.0,
            "pyeong": 25.4,
            "pyeong_category": "중소형",
            "floor": 5,
            "build_year": 2015,
            "deal_amount": 200000,
            "pyeong_price": 7874.0,
            "is_cancel": 0,
            "cancel_date": "",
            "created_at": "2026-09-30 00:00:00"
        },
        {
            "id": "2",
            "deal_date": "2026-09-29",
            "deal_year": 2026,
            "deal_month": 9,
            "deal_day": 29,
            "sido": "경기도",
            "sigungu": "성남시 분당구",
            "sigungu_code": "41135",
            "umd_name": "정자동",
            "apt_name": "단지B",
            "exclusive_area": 59.0,
            "pyeong": 17.8,
            "pyeong_category": "소형",
            "floor": 10,
            "build_year": 2018,
            "deal_amount": 120000,
            "pyeong_price": 6741.5,
            "is_cancel": 1,
            "cancel_date": "2026-09-30",
            "created_at": "2026-09-30 00:00:00"
        }
    ]
    db.upsert_trades(samples)
    
    df_all = db.get_recent_trades(days=30, exclude_canceled=False)
    assert len(df_all) == 2
    
    df_valid = db.get_recent_trades(days=30, exclude_canceled=True)
    assert len(df_valid) == 1
    assert df_valid.iloc[0]["apt_name"] == "단지A"
