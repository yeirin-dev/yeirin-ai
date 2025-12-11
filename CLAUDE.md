# Yeirin-AI

상담의뢰지 기반 상담기관 추천 AI 서비스

## 기술 스택

| 구분 | 기술 |
|------|------|
| Framework | FastAPI |
| Language | Python 3.11+ |
| Package Manager | uv |
| Database | PostgreSQL (읽기 전용) |
| LLM | OpenAI GPT-4o-mini |
| PDF | PyMuPDF |

## 패키지 매니저

```bash
# ⚠️ 반드시 uv 사용
uv sync                    # 의존성 설치
uv sync --all-extras       # 개발 의존성 포함
uv run uvicorn yeirin_ai.main:app --reload --port 8001
```

## 프로젝트 구조

```
yeirin_ai/
├── api/                    # API 라우터
│   └── routes/
│       ├── health.py       # 헬스 체크
│       ├── recommendations.py  # 추천 API
│       ├── documents.py    # 문서 처리 API
│       └── editing.py      # 문서 편집 API
├── core/                   # 설정 및 공통
│   ├── config/
│   │   └── settings.py     # 환경 설정
│   └── models/
│       └── api.py          # API DTO
├── domain/                 # 도메인 모델
│   ├── institution/        # 기관 도메인
│   └── recommendation/     # 추천 도메인
├── infrastructure/         # 인프라 계층
│   ├── database/           # DB 연결 & Repository
│   └── llm/                # OpenAI 클라이언트
├── services/               # 애플리케이션 서비스
│   └── recommendation_service.py
└── main.py                 # 앱 진입점
```

## API 엔드포인트

```bash
# Health Check
GET /api/v1/health

# Recommendations
POST /api/v1/recommendations    # 상담기관 추천

# Documents
POST /api/v1/documents/extract  # PDF 텍스트 추출
POST /api/v1/documents/analyze  # 문서 분석
```

## 주요 명령어

```bash
# 서버 실행
uv run uvicorn yeirin_ai.main:app --reload --port 8001

# 테스트
uv run pytest
uv run pytest --cov=yeirin_ai

# 린트 & 타입 체크
uv run ruff check .
uv run ruff format .
uv run mypy yeirin_ai
```

## MSA 연동

### Yeirin 메인 백엔드에서 호출됨

```bash
# 상담기관 추천 요청
POST http://localhost:8001/api/v1/recommendations
Header: X-Internal-Secret: ${INTERNAL_API_SECRET}
Body: {
  "counsel_request_text": "7세 아들이 ADHD 진단을 받았습니다..."
}

# 응답
{
  "recommendations": [
    {
      "institution_id": "uuid",
      "center_name": "서울아동심리상담센터",
      "score": 0.95,
      "reasoning": "ADHD 전문 상담사 3명...",
      "address": "서울시 강남구...",
      "average_rating": 4.8
    }
  ],
  "total_institutions": 5
}
```

### Database 접근

```bash
# Yeirin 메인 DB 읽기 전용 연결
DATABASE_URL=postgresql://yeirin:yeirin123@localhost:5433/yeirin_dev

# 조회 대상 테이블
- voucher_institutions (기관 정보)
- counselor_profiles (상담사 정보)
- reviews (리뷰 및 평점)
```

## 환경 변수 (.env.example)

```bash
# Database (읽기 전용)
DATABASE_URL=postgresql://yeirin:yeirin123@localhost:5433/yeirin_dev

# OpenAI
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4o-mini

# Application
APP_NAME=yeirin-ai
DEBUG=True
LOG_LEVEL=INFO

# API
API_V1_PREFIX=/api/v1
CORS_ORIGINS=["http://localhost:3000"]
```

## 코드 스타일

```bash
# Ruff 설정 (pyproject.toml)
line-length = 100
target-version = "py311"

# 주요 규칙
E, W, F, I, B, C4, UP
```

## 추천 알고리즘

1. **텍스트 분석**: GPT-4o-mini로 상담의뢰지 의미 분석
2. **기관 매칭**: 전문 분야, 위치, 평점 기반 스코어링
3. **결과 생성**: 상위 5개 기관 + 추천 사유

```python
# 추천 흐름
counsel_request_text → LLM 분석 → DB 기관 조회 → 스코어링 → 결과 반환
```

## 핵심 기능

### 상담기관 추천

- OpenAI GPT-4o-mini 기반 의미론적 분석
- PostgreSQL 기관 데이터 조회
- 기관별 점수 및 추천 사유 제공

### 문서 처리

- PDF 텍스트 추출 (PyMuPDF)
- Playwright 기반 문서 렌더링
- 문서 분석 및 요약
