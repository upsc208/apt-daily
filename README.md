# 🏢 apt-daily: 전국 아파트 실거래가 일일 수집 및 Streamlit 대시보드

공공데이터포털([국토교통부 아파트매매 실거래 상세자료 OpenAPI](https://www.data.go.kr/data/15126469/openapi.do))을 통해 매일 최근 1주일간의 전국 아파트 실거래가를 자동으로 수집하고, **Gemini 2.5 Flash AI 수석 부동산 애널리스트 브리핑** 및 인터랙티브 시각화를 제공하는 100% 무료 서버리스 데이터 파이프라인 시스템입니다.

---

## 🌟 주요 기능

1. **전국 아파트 실거래가 자동 수집**:
   - 전국 약 250개 시군구 법정동 코드(`LAWD_CD`)를 순회하여 최근 7일치 계약 데이터를 수집
   - 단일 SQLite DB(`data/apt_trade.db`)에 중복 없는 증분 Upsert 저장
2. **🤖 Gemini 2.5 Flash 일자별 부동산 애널리스트 브리핑**:
   - 특정 거래 일자를 선택하여 15년 차 수석 애널리스트 관점의 심층 시장 진단 리포트 자동 생성
   - 🎙️ 1줄 헤드라인 & 시장 총평, 🏆 주요 고가·신고가 분석, 📐 지역/평형대 수요 동향, 💡 투자자·실수요자 인사이트
   - **영구 캐싱**: 최초 1회 생성 시 SQLite에 자동 저장되어 다음 조회 시 API 재호출 없이 즉시 로드
3. **📊 인터랙티브 Streamlit 대시보드**:
   - **종합 트렌드 대시보드**: 일자별 거래량·평균 거래금액 시계열 차트 및 시도별 거래량 분포, 평형대별 통계, 최고 평단가 TOP 10 단지, 신고가 갱신 하이라이트
   - **일자별 상세 분석 페이지**: 당일 핵심 지표, Gemini AI 브리핑 카드, 당일 실거래 전체 목록 테이블 및 원클릭 CSV 다운로드
4. **100% 무료 자동화 인프라**:
   - **GitHub Actions**: 매일 아침(KST 06:00) 정기 수집 후 변경된 DB를 자동 커밋 & 푸시
   - **Streamlit Community Cloud**: GitHub 저장소와 연동되어 무료 상시 호스팅 및 데이터 자동 반영

---

## 📁 프로젝트 구조

```
apt-daily/
├── data/
│   ├── apt_trade.db               # 실거래가 및 AI 요약 영속 저장 SQLite DB
│   └── lawd_codes.json            # 전국 250여 개 시군구 법정동 코드 매핑
├── src/
│   ├── __init__.py
│   ├── config.py                  # 설정 및 환경변수 로더
│   ├── collector.py               # 공공데이터 API 수집 및 Mock 생성 모듈
│   ├── database.py                # SQLite 테이블 생성, Upsert, AI 요약 CRUD 매니저
│   ├── ai_analyst.py              # Gemini 2.5 Flash 부동산 애널리스트 분석 모듈
│   └── analytics.py               # KPI 산출, 시계열 집계, 신고가 탐지, 다차원 필터
├── app.py                         # Streamlit 대시보드 메인 애플리케이션 (멀티 메뉴)
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

# 환경 변수 설정
cp .env.example .env
# .env 파일에 DATA_GO_KR_API_KEY 및 GEMINI_API_KEY 입력
```

### 3. 데이터 수집 실행
```bash
# 실제 공공데이터 API 수집 (전국 250개 시군구)
uv run python -m src.collector --days 7

# 강제 샘플(Mock) 데이터 200건 생성
uv run python -m src.collector --mock --count 200
```

### 4. 대시보드 실행
```bash
uv run streamlit run app.py
```
브라우저에서 `http://localhost:8501`로 접속하여 사이드바의 **[📊 종합 트렌드 대시보드]**와 **[📅 일자별 상세 분석 & AI 브리핑]**을 전환하며 확인합니다.

### 5. 테스트 실행
```bash
uv run pytest -v
```
