# 🏢 apt-daily: 전국 아파트 실거래가 일일 수집 및 Streamlit 대시보드

공공데이터포털([국토교통부 아파트매매 실거래 상세자료 OpenAPI](https://www.data.go.kr/data/15126469/openapi.do))을 통해 매일 최근 1주일간의 전국 아파트 실거래가를 자동으로 수집하고, Streamlit으로 인터랙티브 시각화 및 통계를 제공하는 100% 무료 서버리스 데이터 파이프라인 시스템입니다.

---

## 🌟 주요 기능

1. **전국 아파트 실거래가 자동 수집**:
   - 전국 약 250개 시군구 법정동 코드(`LAWD_CD`)를 순회하여 최근 7일치 계약 데이터를 수집
   - 단일 SQLite DB(`data/apt_trade.db`)에 중복 없는 증분 Upsert 저장
2. **인터랙티브 Streamlit 대시보드**:
   - **📊 시장 트렌드 & 차트**: 일자별 거래량·평균 거래금액 시계열 차트 및 시도별 거래량 분포
   - **🏢 평형대 & 평단가 분석**: 소형/중소형/중대형/대형 평형대별 통계 및 최고 평단가 TOP 10 단지
   - **🚀 신고가 갱신 하이라이트**: 동일 단지·동일 면적 기준 최근 7일 내 신고가 갱신 내역 강조
   - **📋 상세 거래 내역 & CSV 다운로드**: 시도/시군구, 평형, 금액 범위 필터링 및 원클릭 CSV 내보내기
3. **100% 무료 자동화 인프라**:
   - **GitHub Actions**: 매일 아침(KST 06:00) 정기 수집 후 변경된 DB를 자동 커밋 & 푸시
   - **Streamlit Community Cloud**: GitHub 저장소와 연동되어 무료 상시 호스팅 및 데이터 자동 반영
4. **Mock / Sample 데이터 모드**:
   - 공공데이터 API 키가 없어도 로컬 개발 및 UI 테스트가 즉시 가능하도록 샘플 데이터 생성기 내장

---

## 📁 프로젝트 구조

```
apt-daily/
├── .github/
│   └── workflows/
│       └── daily_collect.yml      # GitHub Actions 크론 워크플로우 (매일 자동 수집)
├── data/
│   ├── apt_trade.db               # 실거래가 데이터 영속 저장 SQLite DB
│   └── lawd_codes.json            # 전국 250여 개 시군구 법정동 코드 매핑
├── src/
│   ├── __init__.py
│   ├── config.py                  # 설정 및 환경변수 로더
│   ├── collector.py               # 공공데이터 API 수집 및 Mock 생성 모듈
│   ├── database.py                # SQLite 테이블 생성, Upsert, 쿼리 매니저
│   └── analytics.py               # KPI 산출, 시계열 집계, 신고가 탐지, 다차원 필터
├── app.py                         # Streamlit 대시보드 메인 애플리케이션
├── pyproject.toml                 # uv 기반 의존성 정의
├── .env.example                   # 환경변수 템플릿
└── README.md                      # 프로젝트 안내서
```

---

## 🚀 로컬 실행 방법

### 1. 사전 요구사항
- [uv](https://github.com/astral-sh/uv) (초고속 Python 패키지 매니저)

### 2. 설치 및 환경 설정
```bash
# 가상환경 동기화 및 의존성 설치
uv sync

# API 키 설정 (선택 사항: 미설정 시 자동 Mock 모드로 동작)
cp .env.example .env
# .env 파일에 DATA_GO_KR_API_KEY 입력
```

### 3. 데이터 수집 실행
```bash
# 실제 공공데이터 API 수집 (또는 API 키 없을 시 자동 Mock 생성)
uv run python -m src.collector --days 7

# 강제 샘플(Mock) 데이터 200건 생성
uv run python -m src.collector --mock --count 200
```

### 4. 대시보드 실행
```bash
uv run streamlit run app.py
```
브라우저에서 `http://localhost:8501`로 접속하여 대시보드를 확인합니다.

### 5. 테스트 실행
```bash
uv run pytest -v
```

---

## ☁️ 무료 배포 가이드

### 1. GitHub Actions (일일 자동 수집) 설정
1. 이 프로젝트를 GitHub 리포지토리에 푸시합니다.
2. 리포지토리 **Settings > Secrets and variables > Actions** 로 이동합니다.
3. **New repository secret**을 클릭하고 다음을 추가합니다:
   - Name: `DATA_GO_KR_API_KEY`
   - Value: 공공데이터포털에서 발급받은 OpenAPI 일반 인증키
4. 이제 매일 한국 시간 오전 6시(UTC 21:00)에 자동으로 데이터가 수집되어 `data/apt_trade.db`에 커밋됩니다.

### 2. Streamlit Community Cloud 배포
1. [share.streamlit.io](https://share.streamlit.io/)에 접속하여 GitHub 계정으로 로그인합니다.
2. **New app** 버튼을 누르고 본 리포지토리를 선택합니다.
3. Main file path에 `app.py`를 지정하고 **Deploy**를 클릭합니다.
4. 배포가 완료되면 무료 URL이 발급되며, GitHub Actions에 의해 DB가 갱신될 때마다 대시보드에 최신 데이터가 반영됩니다.
