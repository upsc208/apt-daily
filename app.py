import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.database import DatabaseManager
from src.collector import AptTradeCollector
from src.ai_analyst import GeminiAnalyst
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

# Custom CSS for premium aesthetics
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
    .ai-card {
        background: linear-gradient(135deg, #F8FAFC 0%, #EEF2F6 100%);
        border: 1px solid #CBD5E1;
        border-left: 5px solid #3B82F6;
        border-radius: 12px;
        padding: 1.5rem 1.8rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .ai-badge {
        display: inline-block;
        background-color: #DBEAFE;
        color: #1E40AF;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
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

# -------------------------------------------------------------
# Sidebar: Navigation & Controls
# -------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/isometric/100/apartment.png", width=64)
st.sidebar.title("🏢 아파트 실거래가")
st.sidebar.caption("국토교통부 OpenAPI 매일 자동 수집")

# Main Page Navigation
page_mode = st.sidebar.radio(
    "📌 메뉴 선택",
    ["📊 종합 트렌드 대시보드", "📅 일자별 상세 분석 & AI 브리핑"],
    index=0
)

# =============================================================
# VIEW 1: 종합 트렌드 대시보드 (Multi-day Overview)
# =============================================================
if page_mode == "📊 종합 트렌드 대시보드":
    period_options = {
        "최근 7일": 7,
        "최근 14일": 14,
        "최근 30일": 30,
        "전체 데이터": 365
    }
    selected_period_label = st.sidebar.selectbox("📅 조회 기간", list(period_options.keys()), index=0)
    selected_days = period_options[selected_period_label]

    raw_df = db.get_recent_trades(days=selected_days, exclude_canceled=True)

    # Empty DB Seed
    if raw_df.empty:
        st.sidebar.warning("⚠️ 현재 데이터베이스에 실거래 데이터가 없습니다.")
        if st.sidebar.button("📥 실거래 데이터 즉시 수집"):
            with st.spinner("국토교통부 API에서 실거래가를 수집 중입니다..."):
                collector = AptTradeCollector(db_manager=db)
                collector.collect_and_save(days=selected_days)
                st.cache_data.clear()
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 상세 필터")

    sido_list = ["전체"] + sorted(raw_df["sido"].dropna().unique().tolist()) if not raw_df.empty else ["전체"]
    selected_sido = st.sidebar.selectbox("시·도 선택", sido_list)

    if selected_sido != "전체" and not raw_df.empty:
        sigungu_candidates = sorted(raw_df[raw_df["sido"] == selected_sido]["sigungu"].dropna().unique().tolist())
        sigungu_list = ["전체"] + sigungu_candidates
    else:
        sigungu_list = ["전체"] + sorted(raw_df["sigungu"].dropna().unique().tolist()) if not raw_df.empty else ["전체"]

    selected_sigungu = st.sidebar.multiselect("시·군·구 선택", sigungu_list, default=["전체"])

    pyeong_cats = ["전체", "소형", "중소형", "중대형", "대형"]
    selected_cats = st.sidebar.multiselect("평형대 선택", pyeong_cats, default=["전체"])

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

    search_keyword = st.sidebar.text_input("단지명 / 지역명 검색", placeholder="예: 래미안, 은마, 대치동")

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

    st.markdown('<div class="main-title">🏢 전국 아파트 매매 실거래가 종합 대시보드</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-title">조회 기간: <b>{selected_period_label}</b> | 기준일자: <b>{datetime.now().strftime("%Y년 %m월 %d일")}</b></div>', unsafe_allow_html=True)

    if df.empty:
        st.info("💡 선택한 필터 조건에 해당하는 실거래 데이터가 없습니다. 사이드바에서 필터 조건을 조정해 보세요.")
        st.stop()

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

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 시장 트렌드 & 차트",
        "🏢 평형대 & 평단가 분석",
        "🚀 신고가 갱신 하이라이트",
        "📋 실거래가 상세 테이블"
    ])

    with tab1:
        st.subheader("📈 일자별 거래량 및 평균 거래금액 추이")
        daily_trends = compute_daily_trends(df)
        if not daily_trends.empty:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(
                x=daily_trends["deal_date"],
                y=daily_trends["deal_count"],
                name="거래량 (건)",
                marker_color="#3B82F6",
                yaxis="y"
            ))
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
                fig_top.update_layout(yaxis=dict(autorange="reversed"), height=450, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_top, use_container_width=True)

    with tab3:
        st.subheader("🚀 최근 신고가(최고가 갱신) 거래 목록")
        new_highs = detect_new_highs(df)
        if not new_highs.empty:
            st.success(f"총 **{len(new_highs)}건**의 신고가 갱신 거래가 포착되었습니다.")
            display_cols = ["deal_date", "sido", "sigungu", "apt_name", "exclusive_area", "floor", "deal_amount", "pyeong_price"]
            show_highs = new_highs[display_cols].rename(columns={
                "deal_date": "계약일", "sido": "시도", "sigungu": "시군구", "apt_name": "단지명",
                "exclusive_area": "전용면적(m²)", "floor": "층", "deal_amount": "거래금액(만원)", "pyeong_price": "평당가격(만원)"
            })
            st.dataframe(
                show_highs.style.format({"거래금액(만원)": "{:,.0f}", "평당가격(만원)": "{:,.1f}", "전용면적(m²)": "{:.1f}"}),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("조회 기간 내 새롭게 최고가를 갱신한 단지가 없거나 단일 거래입니다.")

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
            "deal_date": "계약일", "sido": "시도", "sigungu": "시군구", "umd_name": "법정동", "apt_name": "단지명",
            "exclusive_area": "전용(m²)", "pyeong": "평형", "pyeong_category": "구분", "floor": "층",
            "build_year": "건축년도", "deal_amount": "거래금액(만원)", "pyeong_price": "평당가(만원)"
        })
        st.dataframe(
            display_df.style.format({"거래금액(만원)": "{:,.0f}", "평당가(만원)": "{:,.1f}", "전용(m²)": "{:.1f}", "평형": "{:.1f}"}),
            use_container_width=True, hide_index=True, height=500
        )

# =============================================================
# VIEW 2: 일자별 상세 분석 & AI 브리핑 (Daily Detail & Gemini AI)
# =============================================================
else:
    st.markdown('<div class="main-title">📅 일자별 실거래 상세 분석 & AI 브리핑</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">특정 거래일자를 선택하여 <b>Gemini 2.5 Flash 부동산 수석 애널리스트</b>의 심층 리포트와 당일 실거래 내역을 확인합니다.</div>', unsafe_allow_html=True)

    available_dates = db.get_available_dates()

    if not available_dates:
        st.warning("⚠️ 저장된 실거래 데이터가 없습니다. 먼저 수집기를 실행하거나 샘플 데이터를 생성해 주세요.")
        if st.button("📥 데이터 즉시 수집"):
            with st.spinner("데이터 수집 중..."):
                collector = AptTradeCollector(db_manager=db)
                collector.collect_and_save(days=7)
                st.cache_data.clear()
                st.rerun()
        st.stop()

    # Date Selector
    selected_date = st.sidebar.selectbox("📅 거래 일자 선택", available_dates, index=0)

    # Load Day Trades
    day_df = db.get_trades_by_date(selected_date, exclude_canceled=True)

    # 1. Day Top Metrics
    st.subheader(f"📌 {selected_date} 거래 핵심 지표")
    day_kpi = compute_kpis(day_df)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("당일 거래건수", f"{day_kpi['total_deals']:,} 건")
    with c2:
        st.metric("당일 총 거래대금", f"{day_kpi['total_amount_eok']:,.1f} 억원")
    with c3:
        st.metric("평균 거래금액", f"{int(day_kpi['avg_amount']):,} 만원")
    with c4:
        st.metric("전국 평균 평단가", f"{int(day_kpi['avg_pyeong_price']):,} 만원/평")
    with c5:
        st.metric("신고가 갱신", f"{day_kpi['new_high_count']:,} 건", delta="🔥 신고가" if day_kpi['new_high_count'] > 0 else None)

    st.markdown("---")

    # 2. AI Analyst Summary Section (Cached in SQLite)
    st.subheader("🤖 Gemini 부동산 수석 애널리스트 Daily Briefing")

    cached_summary = db.get_daily_summary(selected_date)
    analyst = GeminiAnalyst()

    col_btn1, col_btn2 = st.columns([3, 7])

    # If cached summary exists
    if cached_summary:
        with col_btn1:
            st.caption(f"💾 **저장된 리포트 로드됨** (생성일시: {cached_summary['created_at']})")
        with col_btn2:
            if st.button("🔄 AI 분석 리포트 다시 생성하기"):
                with st.spinner("Gemini 2.5 Flash가 시장 데이터를 재분석하고 있습니다..."):
                    new_summary = analyst.generate_summary(day_df, selected_date)
                    db.save_daily_summary(selected_date, new_summary, model_name=analyst.model_name)
                    st.cache_data.clear()
                    st.rerun()

        # Render AI Report Card
        st.markdown(f'<div class="ai-card"><span class="ai-badge">✨ Gemini {cached_summary.get("model_name", "2.5-flash")} 부동산 리포트</span>\n\n{cached_summary["summary_markdown"]}</div>', unsafe_allow_html=True)

    else:
        st.info("💡 아직 이 날짜에 대한 AI 애널리스트 분석 리포트가 생성되지 않았습니다. 아래 버튼을 눌러 최초 1회 생성하면 데이터베이스에 자동 저장됩니다.")
        if st.button("🚀 Gemini AI 애널리스트 분석 리포트 생성하기", type="primary"):
            with st.spinner("Gemini 2.5 Flash가 당일 실거래가 및 신고가 데이터를 심층 분석 중입니다..."):
                generated_summary = analyst.generate_summary(day_df, selected_date)
                db.save_daily_summary(selected_date, generated_summary, model_name=analyst.model_name)
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")

    # 3. Day Detailed Trades Table
    st.subheader(f"📋 {selected_date} 당일 전체 실거래 내역 (총 {len(day_df):,} 건)")

    # Day Filter Controls
    col_f1, col_f2, col_f3 = st.columns([3, 3, 4])
    with col_f1:
        day_sidos = ["전체"] + sorted(day_df["sido"].dropna().unique().tolist())
        sel_day_sido = st.selectbox("시·도 필터", day_sidos, key="day_sido_filter")
    with col_f2:
        day_cats = ["전체", "소형", "중소형", "중대형", "대형"]
        sel_day_cat = st.selectbox("평형대 필터", day_cats, key="day_cat_filter")
    with col_f3:
        day_kw = st.text_input("단지명 / 지역 검색", placeholder="단지명 입력...", key="day_search_kw")

    day_filtered = filter_trades(day_df, {
        "exclude_cancel": True,
        "sido": None if sel_day_sido == "전체" else [sel_day_sido],
        "pyeong_category": None if sel_day_cat == "전체" else [sel_day_cat],
        "keyword": day_kw
    })

    # Download Button
    csv_day = day_filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=f"📥 {selected_date} 실거래 데이터 CSV 다운로드",
        data=csv_day,
        file_name=f"apt_trades_{selected_date}.csv",
        mime="text/csv"
    )

    day_table_cols = [
        "deal_date", "sido", "sigungu", "umd_name", "apt_name",
        "exclusive_area", "pyeong", "pyeong_category", "floor", "build_year",
        "deal_amount", "pyeong_price"
    ]
    day_display_df = day_filtered[day_table_cols].rename(columns={
        "deal_date": "계약일", "sido": "시도", "sigungu": "시군구", "umd_name": "법정동", "apt_name": "단지명",
        "exclusive_area": "전용(m²)", "pyeong": "평형", "pyeong_category": "구분", "floor": "층",
        "build_year": "건축년도", "deal_amount": "거래금액(만원)", "pyeong_price": "평당가(만원)"
    })

    st.dataframe(
        day_display_df.style.format({"거래금액(만원)": "{:,.0f}", "평당가(만원)": "{:,.1f}", "전용(m²)": "{:.1f}", "평형": "{:.1f}"}),
        use_container_width=True,
        hide_index=True,
        height=500
    )
