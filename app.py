import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.database import DatabaseManager
from src.collector import AptTradeCollector
from src.analytics import (
    compute_kpis,
    compute_daily_trends,
    compute_sido_distribution,
    compute_pyeong_distribution,
    detect_new_highs,
    filter_trades
)

# -------------------------------------------------------------
# Streamlit Page Config
# -------------------------------------------------------------
st.set_page_config(
    page_title="전국 아파트 실거래가 대시보드",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich aesthetics
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%);
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 18px;
        border-radius: 8px 8px 0 0;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Data Loading & Caching
# -------------------------------------------------------------
@st.cache_resource
def get_db_manager():
    db = DatabaseManager()
    db.init_db()
    return db

db = get_db_manager()

def load_data(days: int = 7) -> pd.DataFrame:
    df = db.get_recent_trades(days=days, exclude_canceled=True)
    return df

# -------------------------------------------------------------
# Sidebar: Controls & Filters
# -------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/isometric/100/apartment.png", width=64)
st.sidebar.title("🏢 아파트 실거래가")
st.sidebar.caption("국토교통부 OpenAPI 매일 자동 수집")

# Period Selection
period_options = {
    "최근 7일": 7,
    "최근 14일": 14,
    "최근 30일": 30,
    "전체 데이터": 365
}
selected_period_label = st.sidebar.selectbox("📅 조회 기간", list(period_options.keys()), index=0)
selected_days = period_options[selected_period_label]

raw_df = load_data(days=selected_days)

# If database is empty, provide quick seed button
if raw_df.empty:
    st.sidebar.warning("⚠️ 현재 데이터베이스에 저장된 실거래 데이터가 없습니다.")
    if st.sidebar.button("📥 샘플 데이터 200건 즉시 생성"):
        with st.spinner("샘플 실거래가 데이터를 생성 중입니다..."):
            collector = AptTradeCollector(db_manager=db)
            collector.collect_and_save(days=selected_days, use_mock=True, count=200)
            st.cache_data.clear()
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 상세 필터")

# Sido & Sigungu Filter
sido_list = ["전체"] + sorted(raw_df["sido"].dropna().unique().tolist()) if not raw_df.empty else ["전체"]
selected_sido = st.sidebar.selectbox("시·도 선택", sido_list)

if selected_sido != "전체" and not raw_df.empty:
    sigungu_candidates = sorted(raw_df[raw_df["sido"] == selected_sido]["sigungu"].dropna().unique().tolist())
    sigungu_list = ["전체"] + sigungu_candidates
else:
    sigungu_list = ["전체"] + sorted(raw_df["sigungu"].dropna().unique().tolist()) if not raw_df.empty else ["전체"]

selected_sigungu = st.sidebar.multiselect("시·군·구 선택", sigungu_list, default=["전체"])

# Pyeong Category Filter
pyeong_cats = ["전체", "소형", "중소형", "중대형", "대형"]
selected_cats = st.sidebar.multiselect("평형대 선택", pyeong_cats, default=["전체"])

# Price Range Slider
if not raw_df.empty:
    min_price_val = int(raw_df["deal_amount"].min())
    max_price_val = int(raw_df["deal_amount"].max())
else:
    min_price_val, max_price_val = 0, 500000

price_range = st.sidebar.slider(
    "거래금액 범위 (만원)",
    min_value=0,
    max_value=max(max_price_val, 100000),
    value=(0, max(max_price_val, 100000)),
    step=5000,
    format="%d만"
)

# Search Keyword
search_keyword = st.sidebar.text_input("단지명 / 지역명 검색", placeholder="예: 래미안, 은마, 대치동")

# Apply Filters
filter_params = {
    "exclude_cancel": True,
    "sido": None if selected_sido == "전체" else [selected_sido],
    "sigungu": None if "전체" in selected_sigungu or not selected_sigungu else selected_sigungu,
    "pyeong_category": None if "전체" in selected_cats or not selected_cats else selected_cats,
    "min_amount": price_range[0],
    "max_amount": price_range[1],
    "keyword": search_keyword
}

df = filter_trades(raw_df, filter_params)

# -------------------------------------------------------------
# Main Header & Metrics
# -------------------------------------------------------------
st.markdown('<div class="main-title">🏢 전국 아파트 매매 실거래가 일일 대시보드</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-title">조회 기간: <b>{selected_period_label}</b> | 기준일자: <b>{datetime.now().strftime("%Y년 %m월 %d일")}</b></div>', unsafe_allow_html=True)

if df.empty:
    st.info("💡 선택한 필터 조건에 해당하는 실거래 데이터가 없습니다. 사이드바에서 필터 조건을 조정해 보세요.")
    if st.button("🔄 샘플 데이터 생성 및 채우기"):
        collector = AptTradeCollector(db_manager=db)
        collector.collect_and_save(days=selected_days, use_mock=True, count=200)
        st.cache_data.clear()
        st.rerun()
    st.stop()

# Compute KPIs
kpis = compute_kpis(df)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("총 거래건수", f"{kpis['total_deals']:,} 건")
with col2:
    st.metric("총 거래금액", f"{kpis['total_amount_eok']:,.1f} 억원")
with col3:
    st.metric("평균 거래금액", f"{int(kpis['avg_amount']):,} 만원")
with col4:
    st.metric("전국 평균 평단가", f"{int(kpis['avg_pyeong_price']):,} 만원/평")
with col5:
    st.metric("신고가 갱신", f"{kpis['new_high_count']:,} 건", delta="🔥 주목" if kpis['new_high_count'] > 0 else None)

st.markdown("---")

# -------------------------------------------------------------
# Dashboard Tabs
# -------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 시장 트렌드 & 차트",
    "🏢 평형대 & 평단가 분석",
    "🚀 신고가 갱신 하이라이트",
    "📋 실거래가 상세 테이블"
])

# -------------------------------------------------------------
# TAB 1: Market Trends
# -------------------------------------------------------------
with tab1:
    st.subheader("📈 일자별 거래량 및 평균 거래금액 추이")
    daily_trends = compute_daily_trends(df)
    
    if not daily_trends.empty:
        fig_trend = go.Figure()
        
        # Bar: Deal count
        fig_trend.add_trace(go.Bar(
            x=daily_trends["deal_date"],
            y=daily_trends["deal_count"],
            name="거래량 (건)",
            marker_color="#3B82F6",
            yaxis="y"
        ))
        
        # Line: Avg amount
        fig_trend.add_trace(go.Scatter(
            x=daily_trends["deal_date"],
            y=daily_trends["avg_amount"],
            name="평균 거래금액 (만원)",
            mode="lines+markers",
            line=dict(color="#EF4444", width=3),
            yaxis="y2"
        ))
        
        fig_trend.update_layout(
            height=420,
            margin=dict(l=20, r=20, t=30, b=20),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="거래량 (건)", side="left"),
            yaxis2=dict(title="평균 거래금액 (만원)", side="right", overlaying="y", showgrid=False)
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.write("표시할 일자별 데이터가 없습니다.")

    st.subheader("🗺️ 지역(시·도)별 실거래 분포")
    sido_dist = compute_sido_distribution(df)
    
    if not sido_dist.empty:
        fig_sido = px.bar(
            sido_dist,
            x="sido",
            y="count",
            color="avg_pyeong_price",
            color_continuous_scale="Viridis",
            labels={"sido": "시·도", "count": "거래건수", "avg_pyeong_price": "평균 평단가(만원)"},
            title="시·도별 거래량 및 평균 평단가"
        )
        fig_sido.update_layout(height=380, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_sido, use_container_width=True)

# -------------------------------------------------------------
# TAB 2: Pyeong & Price Analysis
# -------------------------------------------------------------
with tab2:
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("📐 평형대별 거래 비중 및 평단가")
        pyeong_dist = compute_pyeong_distribution(df)
        if not pyeong_dist.empty:
            fig_pie = px.pie(
                pyeong_dist,
                names="pyeong_category",
                values="count",
                hole=0.45,
                color="pyeong_category",
                color_discrete_map={
                    "소형": "#60A5FA",
                    "중소형": "#34D399",
                    "중대형": "#FBBF24",
                    "대형": "#F87171"
                }
            )
            fig_pie.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_pie, use_container_width=True)
            
            st.dataframe(
                pyeong_dist.rename(columns={
                    "pyeong_category": "평형대",
                    "count": "거래건수(건)",
                    "avg_amount": "평균 거래금액(만원)",
                    "avg_pyeong_price": "평균 평단가(만원/평)"
                }),
                use_container_width=True,
                hide_index=True
            )
            
    with col_right:
        st.subheader("👑 최고 평단가 TOP 10 단지")
        top_pyeong = df[df["pyeong_price"] > 0].sort_values(by="pyeong_price", ascending=False).head(10)
        if not top_pyeong.empty:
            fig_top = px.bar(
                top_pyeong,
                x="pyeong_price",
                y="apt_name",
                orientation="h",
                color="pyeong_price",
                color_continuous_scale="Reds",
                hover_data=["sigungu", "deal_amount", "exclusive_area", "deal_date"],
                labels={"pyeong_price": "평당 가격 (만원/평)", "apt_name": "아파트 단지명"}
            )
            fig_top.update_layout(
                yaxis=dict(autorange="reversed"),
                height=450,
                margin=dict(l=20, r=20, t=20, b=20)
            )
            st.plotly_chart(fig_top, use_container_width=True)

# -------------------------------------------------------------
# TAB 3: New Highs
# -------------------------------------------------------------
with tab3:
    st.subheader("🚀 최근 신고가(최고가 갱신) 거래 목록")
    new_highs = detect_new_highs(df)
    
    if not new_highs.empty:
        st.success(f"총 **{len(new_highs)}건**의 신고가 갱신 거래가 포착되었습니다.")
        
        display_cols = [
            "deal_date", "sido", "sigungu", "apt_name",
            "exclusive_area", "floor", "deal_amount", "pyeong_price"
        ]
        show_highs = new_highs[display_cols].rename(columns={
            "deal_date": "계약일",
            "sido": "시도",
            "sigungu": "시군구",
            "apt_name": "단지명",
            "exclusive_area": "전용면적(m²)",
            "floor": "층",
            "deal_amount": "거래금액(만원)",
            "pyeong_price": "평당가격(만원)"
        })
        st.dataframe(
            show_highs.style.format({
                "거래금액(만원)": "{:,.0f}",
                "평당가격(만원)": "{:,.1f}",
                "전용면적(m²)": "{:.1f}"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("조회 기간 내 새롭게 최고가를 갱신한 단지가 없거나 단일 거래입니다.")

# -------------------------------------------------------------
# TAB 4: Raw Data Table & Export
# -------------------------------------------------------------
with tab4:
    st.subheader(f"📋 실거래가 전체 목록 (총 {len(df):,} 건)")
    
    col_dl, col_space = st.columns([2, 8])
    with col_dl:
        csv_data = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 CSV 데이터 다운로드",
            data=csv_data,
            file_name=f"apt_trade_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
    table_cols = [
        "deal_date", "sido", "sigungu", "umd_name", "apt_name",
        "exclusive_area", "pyeong", "pyeong_category", "floor", "build_year",
        "deal_amount", "pyeong_price"
    ]
    
    display_df = df[table_cols].rename(columns={
        "deal_date": "계약일",
        "sido": "시도",
        "sigungu": "시군구",
        "umd_name": "법정동",
        "apt_name": "단지명",
        "exclusive_area": "전용(m²)",
        "pyeong": "평형",
        "pyeong_category": "구분",
        "floor": "층",
        "build_year": "건축년도",
        "deal_amount": "거래금액(만원)",
        "pyeong_price": "평당가(만원)"
    })
    
    st.dataframe(
        display_df.style.format({
            "거래금액(만원)": "{:,.0f}",
            "평당가(만원)": "{:,.1f}",
            "전용(m²)": "{:.1f}",
            "평형": "{:.1f}"
        }),
        use_container_width=True,
        hide_index=True,
        height=500
    )
