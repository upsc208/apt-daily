# 전국 아파트 매매 실거래가 일일 수집 및 Streamlit 대시보드 구현 계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 국토교통부 OpenAPI를 통해 최근 1주일간의 전국 아파트 매매 실거래가를 수집해 SQLite에 저장하고, Streamlit으로 인터랙티브 시각화 및 GitHub Actions 일일 자동 수집 파이프라인을 구축한다.

**Architecture:** 전국 250개 시군구 코드 기반 OpenAPI 비동기/배치 수집기(`src/collector.py`)가 계약건을 정제하여 SQLite DB(`src/database.py`)에 증분 저장하고, 분석 모듈(`src/analytics.py`)이 가공한 데이터를 Streamlit 대시보드(`app.py`)에서 Plotly 차트 및 필터로 시각화하며, GitHub Actions가 매일 새벽 정기 수집 및 DB 자동 커밋을 수행한다.

**Tech Stack:** Python 3.11, uv, Streamlit, Plotly, Pandas, httpx, SQLite3, pytest

**Spec:** `docs/superpowers/specs/2026-09-30-apt-daily-dashboard-design.md`

## Global Constraints

- Python 환경 및 패키지 관리는 항상 `uv`만 사용 (`pyproject.toml` 기반)
- 모든 경로는 특별한 경우를 제외하고 프로젝트 루트 기준 상대경로를 사용
- 공공데이터포털 API 키 미설정 시에도 대시보드와 테스트가 완벽히 동작하도록 Mock 데이터 생성기 지원
- Git 저장소 내 관리되는 SQLite DB는 `data/apt_trade.db`에 위치하며 고유 해시 키 기반 Upsert로 중복 저장 방지

## Review Focus

1. **공공데이터포털 API 응답 에러/점검 중**: XML/JSON 에러 응답이나 타임아웃 시 파이프라인이 중단되지 않고 로그 기록 후 다음 시군구로 계속 진행되는지 확인
2. **거래 취소/해제 건 처리**: `is_cancel=1` 및 `cancel_date`가 존재하는 거래 건이 통계 및 대시보드에서 정상 필터링/표시되는지 확인
3. **월 경계(월초) 수집 처리**: 최근 7일이 전월과 당월에 걸쳐 있을 때(예: 10월 3일 기준 9월 26일~10월 3일) 두 달 치 계약년월을 모두 조회하는지 확인
4. **전용면적 및 평형/평단가 변환 정확도**: $m^2$ 단위 전용면적을 평형으로 변환($\div 3.30578$)하고 평당 단가를 정확히 계산하는지 확인
5. **Streamlit 대시보드 빈 데이터 예외 처리**: 필터 조건에 맞는 데이터가 0건일 때 차트나 메트릭이 충돌 없이 안전하게 빈 안내 메시지를 표시하는지 확인

---

### Task 1: 프로젝트 기본 환경 구성 및 시군구 법정동 코드 매핑

**Files:**
- Create: `pyproject.toml`
- Create: `data/lawd_codes.json`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 시스템 환경 변수 (`DATA_GO_KR_API_KEY`)
- Produces: `src.config.Config` (데이터 경로, API 설정, 전국 250개 시군구 코드 매핑 로드 함수 `get_lawd_codes() -> list[dict]`)

- [ ] **Step 1: Write the failing test for Config and Lawd Codes**

```python
# tests/test_config.py
from src.config import Config, get_lawd_codes

def test_config_paths():
    assert Config.DATA_DIR.exists()
    assert Config.DB_PATH.name == "apt_trade.db"

def test_lawd_codes_loading():
    codes = get_lawd_codes()
    assert len(codes) >= 200
    assert any(c["code"] == "11680" and c["sigungu"] == "강남구" for c in codes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'src.config'

- [ ] **Step 3: Implement project config, pyproject.toml, and lawd_codes.json**

`pyproject.toml`에 dependencies(`streamlit`, `pandas`, `plotly`, `httpx`, `python-dotenv`, `pytest`)를 선언하고, 전국 주요 시군구 법정동 코드(서울, 경기, 인천, 5대 광역시 및 전국 시군구 약 250개)를 `data/lawd_codes.json`에 작성하며 `src/config.py`를 구현한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml data/lawd_codes.json src/__init__.py src/config.py tests/test_config.py
git commit -m "chore: setup project config and lawd codes mapping"
```

---

### Task 2: SQLite 데이터베이스 매니저 및 Upsert 구현

**Files:**
- Create: `src/database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: `src.config.Config`
- Produces: 
  - `DatabaseManager.init_db()`
  - `DatabaseManager.upsert_trades(trades: list[dict]) -> int`
  - `DatabaseManager.get_recent_trades(days: int = 7) -> pd.DataFrame`
  - `DatabaseManager.get_total_count() -> int`

- [ ] **Step 1: Write the failing test for DatabaseManager**

```python
# tests/test_database.py
import pytest
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
    
    # Duplicate insert test (Upsert)
    inserted_again = db.upsert_trades(sample)
    assert db.get_total_count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_database.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'src.database'

- [ ] **Step 3: Implement DatabaseManager in `src/database.py`**

SQLite connection context manager, `apt_trades` 테이블 생성 DDL, 인덱스 생성, `INSERT OR REPLACE INTO apt_trades` Upsert 로직 및 데이터 조회 메서드를 구현한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat(database): implement SQLite database manager and upsert logic"
```

---

### Task 3: 공공데이터 API 수집기 및 Mock 데이터 지원 구현

**Files:**
- Create: `src/collector.py`
- Test: `tests/test_collector.py`

**Interfaces:**
- Consumes: `src.config.Config`, `src.database.DatabaseManager`
- Produces:
  - `AptTradeCollector.fetch_period_dates(days: int = 7) -> list[str]`
  - `AptTradeCollector.fetch_lawd_trades(lawd_cd: str, deal_ymd: str) -> list[dict]`
  - `AptTradeCollector.generate_mock_data(days: int = 7) -> list[dict]`
  - `AptTradeCollector.collect_and_save(days: int = 7, use_mock: bool = False) -> int`

- [ ] **Step 1: Write the failing test for AptTradeCollector**

```python
# tests/test_collector.py
from src.collector import AptTradeCollector
from src.database import DatabaseManager

def test_generate_mock_data():
    collector = AptTradeCollector(api_key="")
    mock_data = collector.generate_mock_data(days=7, count=50)
    assert len(mock_data) == 50
    assert "deal_date" in mock_data[0]
    assert "deal_amount" in mock_data[0]
    assert "pyeong_price" in mock_data[0]

def test_collector_collect_mock(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path=db_path)
    db.init_db()
    
    collector = AptTradeCollector(api_key="", db_manager=db)
    saved = collector.collect_and_save(days=7, use_mock=True, count=30)
    assert saved == 30
    assert db.get_total_count() == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collector.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'src.collector'

- [ ] **Step 3: Implement AptTradeCollector in `src/collector.py`**

공공데이터포털 아파트 매매 실거래 상세 자료 OpenAPI 호출, XML/JSON 파싱, 계약일자 필터링, 평형 및 평단가 계산, API 키 부재 시 자동 Mock 데이터 생성 및 CLI 엔트리포인트(`python -m src.collector`)를 구현한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/collector.py tests/test_collector.py
git commit -m "feat(collector): implement public data api collector and mock generator"
```

---

### Task 4: 실거래가 데이터 분석 및 통계 모듈 구현

**Files:**
- Create: `src/analytics.py`
- Test: `tests/test_analytics.py`

**Interfaces:**
- Consumes: `pandas.DataFrame` (실거래가 데이터프레임)
- Produces:
  - `compute_kpis(df: pd.DataFrame) -> dict`
  - `compute_daily_trends(df: pd.DataFrame) -> pd.DataFrame`
  - `compute_pyeong_distribution(df: pd.DataFrame) -> pd.DataFrame`
  - `detect_new_highs(df: pd.DataFrame) -> pd.DataFrame`
  - `filter_trades(df: pd.DataFrame, filters: dict) -> pd.DataFrame`

- [ ] **Step 1: Write the failing test for Analytics**

```python
# tests/test_analytics.py
import pandas as pd
from src.analytics import compute_kpis, detect_new_highs, compute_daily_trends

def test_analytics_kpis():
    data = pd.DataFrame([
        {"id": "1", "deal_date": "2026-09-28", "deal_amount": 100000, "pyeong_price": 3000, "is_cancel": 0, "sido": "서울", "apt_name": "A", "exclusive_area": 84.0},
        {"id": "2", "deal_date": "2026-09-29", "deal_amount": 200000, "pyeong_price": 6000, "is_cancel": 0, "sido": "서울", "apt_name": "A", "exclusive_area": 84.0},
    ])
    kpi = compute_kpis(data)
    assert kpi["total_deals"] == 2
    assert kpi["avg_amount"] == 150000
    assert kpi["avg_pyeong_price"] == 4500

def test_detect_new_highs():
    data = pd.DataFrame([
        {"id": "1", "deal_date": "2026-09-25", "sido": "서울", "sigungu": "강남구", "apt_name": "은마", "exclusive_area": 84.0, "deal_amount": 240000, "is_cancel": 0},
        {"id": "2", "deal_date": "2026-09-29", "sido": "서울", "sigungu": "강남구", "apt_name": "은마", "exclusive_area": 84.0, "deal_amount": 260000, "is_cancel": 0},
    ])
    new_highs = detect_new_highs(data)
    assert len(new_highs) >= 1
    assert new_highs.iloc[-1]["deal_amount"] == 260000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_analytics.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'src.analytics'

- [ ] **Step 3: Implement data analysis functions in `src/analytics.py`**

KPI 집계, 일자별 거래량/평균가 시계열 계산, 평형대별 분포 계산, 동일 단지·동일 전용면적 기준 신고가 갱신 탐지 알고리즘 및 다차원 필터링 함수를 구현한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_analytics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): implement statistical aggregation and new-high detection"
```

---

### Task 5: Streamlit 인터랙티브 대시보드 UI 구현

**Files:**
- Create: `app.py`
- Create: `tests/test_app.py`

**Interfaces:**
- Consumes: `src.database.DatabaseManager`, `src.analytics`, `src.collector.AptTradeCollector`
- Produces: 웹 인터페이스 (`streamlit run app.py`)

- [ ] **Step 1: Write tests for Streamlit helper logic & data loader**

```python
# tests/test_app.py
from src.database import DatabaseManager
from src.collector import AptTradeCollector
from src.analytics import compute_kpis

def test_dashboard_data_loading(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path=db_path)
    db.init_db()
    collector = AptTradeCollector(api_key="", db_manager=db)
    collector.collect_and_save(days=7, use_mock=True, count=20)
    
    df = db.get_recent_trades(days=7)
    assert not df.empty
    kpi = compute_kpis(df)
    assert kpi["total_deals"] == 20
```

- [ ] **Step 2: Run test to verify data pipeline integration**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS

- [ ] **Step 3: Implement Streamlit Dashboard in `app.py`**

- Streamlit 페이지 설정 (타이틀, 레이아웃, 파비콘)
- 상단 KPI 메트릭 카드 (총 거래건수, 총 거래금액, 전국 평균 평단가, 최고 거래가, 신고가 건수)
- 사이드바 다차원 필터 (기간, 시도/시군구, 평형대, 금액 범위 슬라이더, 데이터 새로고침/수집 트리거)
- 4대 메인 탭:
  1. 📊 시장 트렌드 & 차트 (일자별 거래량/평균금액 바·라인 차트, 지역별 거래량 랭킹)
  2. 🏢 평형대 & 평단가 분석 (평형대별 평단가 Box Plot 및 상위 평단가 단지)
  3. 🚀 신고가 하이라이트 (최고가 경신 거래 목록 및 상승폭 강조 카드)
  4. 📋 실거래가 상세 테이블 & CSV 다운로드 버튼
- DB가 비어있는 경우 자동 샘플 데이터 채우기 버튼 및 안내 제공

- [ ] **Step 4: Run Streamlit script validation**

Run: `uv run python -c "import app; print('App module syntax OK')"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat(dashboard): implement rich interactive Streamlit dashboard"
```

---

### Task 6: GitHub Actions 일일 자동 수집 워크플로우 및 배포 문서 작성

**Files:**
- Create: `.github/workflows/daily_collect.yml`
- Create: `.env.example`
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Write `.github/workflows/daily_collect.yml`**

매일 UTC 21:00 (한국 시간 06:00) 스케줄 크론 및 `workflow_dispatch` 설정, `astral-sh/setup-uv` 액션을 활용한 자동 수집 실행 및 `data/apt_trade.db` 변경 시 자동 Git 커밋 & 푸시 워크플로우 작성.

- [ ] **Step 2: Write `.env.example`, `.gitignore`, and comprehensive `README.md`**

환경 변수 가이드, GitHub Secrets 설정법, Streamlit Community Cloud 배포 방법, 로컬 실행 방법(`uv run streamlit run app.py`)을 포함한 한글 가이드 작성.

- [ ] **Step 3: End-to-end integration test (Full collection + DB + Analytics + App check)**

Run: `uv run python -m src.collector --mock --count 100 && uv run pytest -v`
Expected: 모든 테스트 PASS (0 failures)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/daily_collect.yml .env.example .gitignore README.md
git commit -m "feat(ci): add GitHub Actions daily collection workflow and documentation"
```
