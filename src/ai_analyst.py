import os
import json
import httpx
import pandas as pd
from datetime import datetime
try:
    from src.config import Config
    from src.analytics import compute_kpis, compute_sido_distribution, compute_pyeong_distribution, detect_new_highs
except ImportError:
    from .config import Config
    from .analytics import compute_kpis, compute_sido_distribution, compute_pyeong_distribution, detect_new_highs

class GeminiAnalyst:
    def __init__(self, api_key: str | None = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

    def build_prompt(self, df: pd.DataFrame, deal_date: str) -> str:
        """Construct a rich prompt for Gemini containing key statistics of the day."""
        if df.empty:
            return f"{deal_date} 기준 등록된 아파트 실거래 데이터가 없습니다."

        kpi = compute_kpis(df)
        sido_dist = compute_sido_distribution(df).head(5)
        pyeong_dist = compute_pyeong_distribution(df)
        new_highs = detect_new_highs(df)

        # Top 5 most expensive transactions
        top_trades = df.sort_values(by="deal_amount", ascending=False).head(5)
        top_trades_text = "\n".join([
            f"- {row['sido']} {row['sigungu']} {row['apt_name']} ({row.get('exclusive_area', 0):.1f}m², {row.get('floor', 0)}층): {row['deal_amount']:,}만원 (평당 {row.get('pyeong_price', 0):,.1f}만원)"
            for _, row in top_trades.iterrows()
        ])

        # Top 5 New Highs
        new_highs_text = "해당 일자에는 확인된 신고가 거래가 없습니다."
        if not new_highs.empty:
            new_highs_text = "\n".join([
                f"- {row['sido']} {row['sigungu']} {row['apt_name']} ({row.get('exclusive_area', 0):.1f}m²): {row['deal_amount']:,}만원 (평당 {row.get('pyeong_price', 0):,.1f}만원)"
                for _, row in new_highs.head(5).iterrows()
            ])

        # Region stats
        sido_text = ", ".join([f"{r['sido']}({r['count']}건, 평당 {r['avg_pyeong_price']:,.0f}만)" for _, r in sido_dist.iterrows()])

        # Pyeong stats
        pyeong_text = ", ".join([f"{r['pyeong_category']}({r['count']}건, 평균 {int(r['avg_amount']):,}만)" for _, r in pyeong_dist.iterrows()])

        prompt = f"""
당신은 대한민국 부동산 시장을 15년 이상 분석해 온 **부동산 수석 수석 애널리스트**입니다.
아래 제공된 **{deal_date} 당일 국토교통부 아파트 매매 실거래가 원천 데이터 통계**를 바탕으로 투자자와 실수요자를 위한 깊이 있고 신뢰도 높은 **일일 시장 분석 브리핑 리포트**를 작성해 주세요.

### 📊 {deal_date} 당일 거래 핵심 데이터 요약
- **총 거래건수**: {kpi['total_deals']:,}건
- **총 거래대금**: {kpi['total_amount_eok']:,}억원
- **평균 거래금액**: {int(kpi['avg_amount']):,}만원
- **전국 평균 평단가**: {int(kpi['avg_pyeong_price']):,}만원/평
- **당일 최고가 거래 단지**: {kpi['max_apt']} ({kpi['max_amount']:,}만원)
- **신고가(최고가 갱신) 거래건수**: {kpi['new_high_count']:,}건

### 🏆 당일 최고가 거래 TOP 5
{top_trades_text}

### 🚀 당일 주요 신고가(최고가 갱신) 내역
{new_highs_text}

### 🗺️ 주요 지역별 거래 현황
{sido_text}

### 📐 평형대별 거래 현황
{pyeong_text}

---
### 📝 리포트 작성 가이드라인 (다음 4개 섹션의 마크다운 포맷 준수)
1. **🎙️ 1줄 헤드라인 & 시장 총평**: 당일 거래 활성도, 시장 분위기(상승세/관망세/양극화 등)를 1줄 헤드라인과 함께 간결하고 힘있게 요약.
2. **🏆 주요 고가 및 신고가 거래 분석**: 당일 최고가 및 신고가 거래의 특징, 주도 지역과 단지가 가지는 시장적 의미 분석.
3. **📐 지역 및 평형대별 수요 동향**: 수도권 vs 지방 거래 격차, 실수요자 중심의 선호 평형대(중소형 vs 중대형) 흐름 진단.
4. **💡 애널리스트 인사이트 & 관전 포인트**: 현재 거래 흐름을 바탕으로 내 집 마련 실수요자 및 투자자가 주목해야 할 핵심 조언.

*톤앤매너: 전문적이고 객관적이면서도 통찰력 있는 어조. 가독성이 좋도록 마크다운(볼드체, 글머리기호, 하이라이트)을 적극 활용할 것.*
"""
        return prompt.strip()

    def generate_fallback_summary(self, df: pd.DataFrame, deal_date: str) -> str:
        """Generate high-quality rule-based statistical summary when API key is unavailable."""
        if df.empty:
            return f"### 📅 {deal_date} 부동산 시장 일일 브리핑\n\n해당 일자에는 등록된 아파트 실거래 데이터가 없습니다."

        kpi = compute_kpis(df)
        sido_dist = compute_sido_distribution(df).head(3)
        top_apt = df.sort_values(by="deal_amount", ascending=False).iloc[0] if not df.empty else None

        sido_summary = ", ".join([f"**{r['sido']}**({r['count']:,}건)" for _, r in sido_dist.iterrows()])

        return f"""### 🎙️ {deal_date} 아파트 실거래 시장 브리핑 (규칙 기반 분석)

> **핵심 요약**: 당일 전국에서 총 **{kpi['total_deals']:,}건**의 실거래가 체결되었으며, 총 거래 대금은 **{kpi['total_amount_eok']:,.1f}억원** 규모입니다.

---

#### 🏆 1. 당일 최고가 및 주요 거래
* **당일 최고가 단지**: {top_apt['sido']} {top_apt['sigungu']} **{top_apt['apt_name']}** (전용 {top_apt['exclusive_area']:.1f}m², {top_apt['floor']}층)
* **거래 금액**: **{top_apt['deal_amount']:,}만원** (평당 약 {top_apt.get('pyeong_price', 0):,.0f}만원/평)
* **신고가 포착**: 당일 약 **{kpi['new_high_count']:,}건**의 신고가 갱신 거래가 확인되었습니다.

#### 🗺️ 2. 지역별 거래 활성도
* 가장 많은 거래가 이루어진 상위 지역은 {sido_summary} 순입니다.
* 전국 평균 거래금액은 약 **{int(kpi['avg_amount']):,}만원**, 평균 평단가는 **{int(kpi['avg_pyeong_price']):,}만원/평**을 기록했습니다.

#### 💡 3. 시장 관전 포인트
* 고가 주거지와 선호 입지를 중심으로 거래가 집중되는 양상을 보이고 있습니다.
* 실시간 Gemini AI 분석을 원하시면 `.env` 파일에 `GEMINI_API_KEY`를 설정해 주세요.
"""

    def generate_summary(self, df: pd.DataFrame, deal_date: str) -> str:
        """Generate AI analyst summary using Gemini API or fallback."""
        if df.empty:
            return f"### 📅 {deal_date} 부동산 시장 일일 브리핑\n\n해당 일자에는 등록된 아파트 실거래 내역이 확인되지 않았습니다."

        if not self.api_key:
            return self.generate_fallback_summary(df, deal_date)

        prompt = self.build_prompt(df, deal_date)
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 2048
            }
        }

        try:
            url = f"{self.api_url}?key={self.api_key}"
            response = httpx.post(url, json=payload, timeout=25.0)
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text_parts = candidates[0].get("content", {}).get("parts", [])
                    if text_parts:
                        return text_parts[0].get("text", "").strip()
            # If API fails (e.g. invalid key or quota), return fallback
            return self.generate_fallback_summary(df, deal_date)
        except Exception:
            return self.generate_fallback_summary(df, deal_date)
