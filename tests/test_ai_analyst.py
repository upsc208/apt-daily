import pytest
import pandas as pd
from src.ai_analyst import GeminiAnalyst

@pytest.fixture
def sample_daily_df():
    return pd.DataFrame([
        {
            "id": "1",
            "deal_date": "2026-09-30",
            "deal_year": 2026,
            "deal_month": 9,
            "deal_day": 30,
            "sido": "서울특별시",
            "sigungu": "강남구",
            "umd_name": "대치동",
            "apt_name": "은마",
            "exclusive_area": 84.0,
            "pyeong": 25.4,
            "pyeong_category": "중소형",
            "floor": 10,
            "deal_amount": 260000,
            "pyeong_price": 10236.2,
            "is_cancel": 0
        },
        {
            "id": "2",
            "deal_date": "2026-09-30",
            "deal_year": 2026,
            "deal_month": 9,
            "deal_day": 30,
            "sido": "경기도",
            "sigungu": "성남시 분당구",
            "umd_name": "정자동",
            "apt_name": "파크뷰",
            "exclusive_area": 114.0,
            "pyeong": 34.5,
            "pyeong_category": "중대형",
            "floor": 15,
            "deal_amount": 195000,
            "pyeong_price": 5652.2,
            "is_cancel": 0
        }
    ])

def test_build_prompt(sample_daily_df):
    analyst = GeminiAnalyst(api_key="")
    prompt = analyst.build_prompt(sample_daily_df, "2026-09-30")
    assert "2026-09-30" in prompt
    assert "은마" in prompt
    assert "파크뷰" in prompt
    assert "애널리스트" in prompt

def test_fallback_summary_generation(sample_daily_df):
    analyst = GeminiAnalyst(api_key="")
    summary = analyst.generate_fallback_summary(sample_daily_df, "2026-09-30")
    assert "2026-09-30" in summary
    assert "총 거래" in summary or "브리핑" in summary
    assert "은마" in summary or "파크뷰" in summary

def test_generate_summary_without_key_uses_fallback(sample_daily_df):
    analyst = GeminiAnalyst(api_key="")
    summary = analyst.generate_summary(sample_daily_df, "2026-09-30")
    assert len(summary) > 50
    assert "2026-09-30" in summary

def test_empty_dataframe_handling():
    analyst = GeminiAnalyst(api_key="")
    summary = analyst.generate_summary(pd.DataFrame(), "2026-09-30")
    assert "거래 데이터가 없습니다" in summary or "거래 내역이 확인되지 않았습니다" in summary
