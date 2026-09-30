import pytest
import pandas as pd
from src.analytics import (
    compute_kpis,
    compute_daily_trends,
    compute_sido_distribution,
    compute_pyeong_distribution,
    detect_new_highs,
    filter_trades
)

@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "id": "1",
            "deal_date": "2026-09-25",
            "deal_year": 2026,
            "deal_month": 9,
            "deal_day": 25,
            "sido": "서울특별시",
            "sigungu": "강남구",
            "apt_name": "은마",
            "exclusive_area": 84.0,
            "pyeong": 25.4,
            "pyeong_category": "중소형",
            "floor": 7,
            "deal_amount": 240000,
            "pyeong_price": 9448.8,
            "is_cancel": 0
        },
        {
            "id": "2",
            "deal_date": "2026-09-28",
            "deal_year": 2026,
            "deal_month": 9,
            "deal_day": 28,
            "sido": "서울특별시",
            "sigungu": "강남구",
            "apt_name": "은마",
            "exclusive_area": 84.0,
            "pyeong": 25.4,
            "pyeong_category": "중소형",
            "floor": 10,
            "deal_amount": 260000,  # New high for 은마 84.0m2
            "pyeong_price": 10236.2,
            "is_cancel": 0
        },
        {
            "id": "3",
            "deal_date": "2026-09-29",
            "deal_year": 2026,
            "deal_month": 9,
            "deal_day": 29,
            "sido": "경기도",
            "sigungu": "성남시 분당구",
            "apt_name": "파크뷰",
            "exclusive_area": 59.0,
            "pyeong": 17.8,
            "pyeong_category": "소형",
            "floor": 15,
            "deal_amount": 140000,
            "pyeong_price": 7865.2,
            "is_cancel": 0
        },
        {
            "id": "4",
            "deal_date": "2026-09-29",
            "deal_year": 2026,
            "deal_month": 9,
            "deal_day": 29,
            "sido": "부산광역시",
            "sigungu": "해운대구",
            "apt_name": "엘시티",
            "exclusive_area": 144.0,
            "pyeong": 43.6,
            "pyeong_category": "대형",
            "floor": 45,
            "deal_amount": 350000,
            "pyeong_price": 8027.5,
            "is_cancel": 0
        }
    ])

def test_compute_kpis(sample_df):
    kpi = compute_kpis(sample_df)
    assert kpi["total_deals"] == 4
    assert kpi["max_amount"] == 350000
    assert "엘시티" in kpi["max_apt"]
    assert kpi["avg_amount"] == 247500.0
    assert kpi["total_amount_eok"] == pytest.approx(99.0, rel=1e-2)

def test_compute_kpis_empty():
    kpi = compute_kpis(pd.DataFrame())
    assert kpi["total_deals"] == 0
    assert kpi["avg_amount"] == 0.0

def test_compute_daily_trends(sample_df):
    trends = compute_daily_trends(sample_df)
    assert not trends.empty
    assert "deal_date" in trends.columns
    assert "deal_count" in trends.columns
    assert "avg_amount" in trends.columns
    assert len(trends) == 3  # 3 distinct dates

def test_compute_sido_distribution(sample_df):
    sido_dist = compute_sido_distribution(sample_df)
    assert len(sido_dist) == 3
    assert sido_dist.iloc[0]["sido"] == "서울특별시"
    assert sido_dist.iloc[0]["count"] == 2

def test_compute_pyeong_distribution(sample_df):
    pyeong_dist = compute_pyeong_distribution(sample_df)
    assert "pyeong_category" in pyeong_dist.columns
    assert len(pyeong_dist) == 3  # 소형, 중소형, 대형

def test_detect_new_highs(sample_df):
    new_highs = detect_new_highs(sample_df)
    assert not new_highs.empty
    # 은마 (2026-09-28, 260,000) should be identified as a new high compared to earlier 240,000
    eunma_record = new_highs[new_highs["apt_name"] == "은마"]
    assert len(eunma_record) == 1
    assert eunma_record.iloc[0]["deal_amount"] == 260000

def test_filter_trades(sample_df):
    filtered = filter_trades(sample_df, {
        "sido": ["서울특별시"],
        "min_amount": 250000,
        "pyeong_category": ["중소형"]
    })
    assert len(filtered) == 1
    assert filtered.iloc[0]["apt_name"] == "은마"
    assert filtered.iloc[0]["deal_amount"] == 260000
