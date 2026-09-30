# 전국 아파트 매매 실거래가 일일 수집 및 Streamlit 대시보드 시스템 설계서

## 1. 개요 (Overview)

본 프로젝트는 공공데이터포털(국토교통부 아파트매매 실거래 상세 자료 OpenAPI)을 통해 매일 최근 1주일간의 전국 아파트 매매 실거래가를 자동으로 수집하고, SQLite 데이터베이스에 누적 저장한 후, Streamlit 기반의 대시보드를 통해 직관적인 통계 및 시각화를 제공하는 무료 서버리스 기반 데이터 파이프라인 시스템이다.

### 1.1 목표 및 주요 특징
- **전국 데이터 자동 수집**: 전국 약 250개 시군구 법정동 코드(`LAWD_CD`)를 순회하여 최근 7일간의 계약 건을 매일 수집
- **경량 영속 저장소**: 단일 파일 기반 SQLite DB(`data/apt_trade.db`)를 사용하여 중복 방지(Upsert) 및 롤링 보관
- **인터랙티브 대시보드**: Streamlit과 Plotly를 활용하여 지역별/기간별 필터, 일자별 거래량/금액 추이, 평형대별 평단가 분석, 신고가 갱신 하이라이트 제공
- **100% 무료 자동화 배포**: GitHub Actions(일일 배치 크론) + Streamlit Community Cloud 호스팅을 연계한 완전 무료 운영
- **개발 편의성**: 로컬 `.env` 지원 및 API 키 미등록 시 자동 Mock/Sample 데이터 모드 지원

---

## 2. 시스템 아키텍처 (System Architecture)

```
+-------------------------------------------------------------+
|                      GitHub Actions Cron                    |
|                (매일 06:00 KST / 21:00 UTC)                  |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                    Collector (src/collector.py)             |
|   - 전국 법정동 시군구 코드 (data/lawd_codes.json) 로드        |
|   - 공공데이터포털 OpenAPI 호출 (최근 7일 계약건)               |
|   - XML/JSON 응답 파싱 및 데이터 정제                           |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                 Database (src/database.py)                  |
|   - SQLite DB (data/apt_trade.db)                           |
|   - 고유 해시 키 기반 Upsert (중복 제거)                       |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|              Git Auto Commit & Push to GitHub               |
|            (수집 완료된 apt_trade.db 자동 반영)              |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                 Streamlit Community Cloud                   |
|   - app.py 실행                                             |
|   - SQLite 데이터 로드 및 src/analytics.py 분석 집계         |
|   - 인터랙티브 UI/차트 (Plotly) 렌더링                         |
+-------------------------------------------------------------+
```

---

## 3. 모듈별 상세 설계 (Component Design)

### 3.1 디렉토리 및 파일 구성
```
apt-daily/
├── .github/
│   └── workflows/
│       └── daily_collect.yml      # GitHub Actions 크론 워크플로우
├── data/
│   ├── apt_trade.db               # 실거래가 데이터 저장 SQLite DB
│   └── lawd_codes.json            # 전국 시군구 법정동 코드 매핑 (약 250개)
├── src/
│   ├── __init__.py
│   ├── config.py                  # 환경변수, 경로, API 기본값 설정
│   ├── collector.py               # 공공데이터 API 호출 및 파싱 모듈
│   ├── database.py                # SQLite 초기화, 트랜잭션 및 Upsert 모듈
│   └── analytics.py               # 데이터 정제, 평형 계산, 신고가 판별, 통계
├── app.py                         # Streamlit 대시보드 메인 애플리케이션
├── pyproject.toml                 # uv 패키지 의존성 정의
├── .env.example                   # 환경변수 템플릿
└── README.md                      # 프로젝트 설치 및 실행 가이드
```

### 3.2 데이터베이스 스키마 (`data/apt_trade.db`)

테이블명: `apt_trades`

| 컬럼명 | 타입 | 제약 조건 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | 중복 방지용 고유 해시 (지역코드+계약일+단지명+층+전용면적) |
| `deal_date` | TEXT | NOT NULL | 계약일자 (`YYYY-MM-DD`) |
| `deal_year` | INTEGER | NOT NULL | 계약년도 |
| `deal_month` | INTEGER | NOT NULL | 계약월 |
| `deal_day` | INTEGER | NOT NULL | 계약일 |
| `sido` | TEXT | NOT NULL | 시·도 (예: 서울특별시, 경기도) |
| `sigungu` | TEXT | NOT NULL | 시·군·구 (예: 강남구, 분당구) |
| `sigungu_code` | TEXT | NOT NULL | 5자리 법정동 코드 (예: 11680) |
| `umd_name` | TEXT | | 법정동/읍면동 (예: 역삼동) |
| `apt_name` | TEXT | NOT NULL | 아파트 단지명 |
| `exclusive_area` | REAL | NOT NULL | 전용면적 ($m^2$) |
| `pyeong` | REAL | NOT NULL | 평형 (전용면적 / 3.30578) |
| `pyeong_category` | TEXT | NOT NULL | 평형대 분류 (소형: 20평 미만, 중소형: 20~30평, 중대형: 30~40평, 대형: 40평 이상) |
| `floor` | INTEGER | | 층수 |
| `build_year` | INTEGER | | 건축년도 |
| `deal_amount` | INTEGER | NOT NULL | 거래금액 (단위: 만원) |
| `pyeong_price` | REAL | NOT NULL | 평당 가격 (단위: 만원/평) |
| `is_cancel` | INTEGER | DEFAULT 0 | 해제여부 (1: 해제, 0: 정상) |
| `cancel_date` | TEXT | | 해제사유발생일 |
| `created_at` | TEXT | NOT NULL | 데이터 수집 및 등록 일시 |

**인덱스**:
- `idx_deal_date` on `apt_trades(deal_date)`
- `idx_sido_sigungu` on `apt_trades(sido, sigungu)`
- `idx_apt_name` on `apt_trades(apt_name)`

### 3.3 수집기 (Collector) 상세 설계
- **API 엔드포인트**: `http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev` (국토교통부 아파트매매 실거래 상세 자료)
- **파라미터**: `LAWD_CD` (시군구코드 5자리), `DEAL_YMD` (계약년월 6자리), `serviceKey`, `pageNo`, `numOfRows=1000`
- **수집 범위**: 오늘 기준 최근 7일의 계약일자를 포함하는 계약년월(월 경계 포함 시 당월 및 전월)
- **속도 및 에러 처리**:
  - `httpx` 비동기 또는 적절한 간격의 재시도(Retry with backoff) 처리
  - 일일 호출 실패 시 로그 출력 및 다음 시군구 연속 진행
  - API 키 미제공 시 테스트 및 대시보드 검증을 위한 Mock 데이터 생성기 내장

### 3.4 대시보드 UI (Streamlit) 설계
- **Header & Metric Cards**:
  - 최근 7일 총 거래건수, 총 거래금액, 전국 평균 평단가, 신고가 갱신 건수
- **Sidebar Filters**:
  - 조회 기간 선택 (최근 7일, 최근 3일, 당일, 사용자 지정)
  - 시·도 및 시·군·구 다중/단일 선택
  - 금액 범위 및 평형대 필터 슬라이더
- **Main Tabs**:
  1. 📊 **시장 트렌드 & 차트**:
     - 일자별 거래량 및 평균 거래금액 추이 (Plotly 혼합 바/라인 차트)
     - 지역별(시도) 거래량 랭킹 Bar 차트
  2. 🏢 **평형대 & 평단가 분석**:
     - 평형대별 평균 거래금액 및 평단가 비교 Box plot
     - 주요 단지별 평단가 상위 순위
  3. 🚀 **신고가 하이라이트**:
     - 최근 7일 내 단지·면적별 기존 최고가를 경신한 거래 내역 강조 표
  4. 📋 **상세 거래 내역 & 다운로드**:
     - 필터링된 실거래가 데이터테이블 (정렬/검색 지원)
     - CSV 다운로드 버튼 제공

---

## 4. GitHub Actions 워크플로우 설계

`.github/workflows/daily_collect.yml`
```yaml
name: Daily APT Trade Data Collection

on:
  schedule:
    - cron: '0 21 * * *' # 매일 KST 06:00 (UTC 21:00)
  workflow_dispatch:      # 수동 실행 지원

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v5
        
      - name: Set up Python
        run: uv python install 3.11
        
      - name: Install dependencies
        run: uv sync
        
      - name: Run Collector
        env:
          DATA_GO_KR_API_KEY: ${{ secrets.DATA_GO_KR_API_KEY }}
        run: uv run python -m src.collector
        
      - name: Commit and Push DB
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/apt_trade.db
          git diff --quiet && git diff --staged --quiet || (git commit -m "chore(data): auto update apt trade data [skip ci]" && git push)
```

---

## 5. 보안 및 환경 설정

- **API 키 관리**:
  - 로컬 환경: `.env` 파일에 `DATA_GO_KR_API_KEY=your_key_here` 저장 (`.gitignore`에 추가)
  - GitHub Actions: Repository Secrets에 `DATA_GO_KR_API_KEY` 등록
  - Streamlit Cloud: Settings > Secrets에 필요 시 등록
- **배포 안전성**:
  - API Key가 누락되거나 유효하지 않은 경우에도 대시보드가 정상 동작할 수 있도록 Mock/기존 DB 데이터 로드 Fallback 메커니즘 구비

---

## 6. 검증 및 테스트 계획

1. **DB 매니저 단위 테스트**: SQLite 테이블 생성, 중복 데이터 삽입 시 고유키 기반 Upsert 동작 확인
2. **API 수집 및 Mock 테스트**: 국토교통부 API XML/JSON 파싱 및 정제, Mock 데이터 생성 및 적재 확인
3. **대시보드 기능 테스트**: 필터 조작, Plotly 차트 렌더링, CSV 다운로드, 신고가 계산 로직 검증
4. **워크플로우 검증**: GitHub Actions yaml 문법 및 로컬 배치 시뮬레이션 확인
