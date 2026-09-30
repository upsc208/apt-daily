import pytest
from datetime import datetime, timedelta
from src.collector import AptTradeCollector
from src.database import DatabaseManager

def test_generate_mock_data():
    collector = AptTradeCollector(api_key="")
    mock_data = collector.generate_mock_data(days=7, count=50)
    assert len(mock_data) == 50
    item = mock_data[0]
    assert "id" in item
    assert "deal_date" in item
    assert "deal_amount" in item
    assert "pyeong_price" in item
    assert "pyeong_category" in item
    assert item["pyeong_category"] in ["소형", "중소형", "중대형", "대형"]

def test_get_target_deal_ymds():
    collector = AptTradeCollector(api_key="")
    # For a 7-day period, target YMDs should return at least 1 or 2 strings (YYYYMM)
    ymds = collector.get_target_deal_ymds(days=7)
    assert len(ymds) >= 1
    assert all(len(ymd) == 6 and ymd.isdigit() for ymd in ymds)

def test_collector_collect_mock(tmp_path):
    db_path = tmp_path / "test_collect.db"
    db = DatabaseManager(db_path=db_path)
    db.init_db()
    
    collector = AptTradeCollector(api_key="", db_manager=db)
    saved = collector.collect_and_save(days=7, use_mock=True, count=40)
    assert saved == 40
    assert db.get_total_count() == 40

def test_parse_api_item():
    collector = AptTradeCollector(api_key="")
    raw_item = {
        "dealYear": "2026",
        "dealMonth": "9",
        "dealDay": "29",
        "sggCd": "11680",
        "aptNm": "대치은마",
        "excluUseAr": "84.43",
        "floor": "7",
        "buildYear": "1979",
        "dealAmount": " 280,000 ",
        "umdNm": "대치동",
        "cdealType": "",
        "cdealDay": ""
    }
    sido_map = {"11680": ("서울특별시", "강남구")}
    parsed = collector.parse_trade_item(raw_item, sido_map)
    assert parsed is not None
    assert parsed["deal_date"] == "2026-09-29"
    assert parsed["deal_amount"] == 280000
    assert parsed["sido"] == "서울특별시"
    assert parsed["sigungu"] == "강남구"
    assert parsed["apt_name"] == "대치은마"
    assert parsed["pyeong"] == pytest.approx(84.43 / 3.30578, rel=1e-2)
