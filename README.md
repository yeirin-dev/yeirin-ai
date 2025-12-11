# Yeirin AI - AI 기반 상담 기관 추천 서비스

FastAPI 기반 RAG(Retrieval-Augmented Generation) 상담 기관 추천 서비스

## 개요

상담 의뢰지 텍스트를 분석하여 가장 적합한 바우처 상담 기관을 추천하는 AI 서비스입니다.
OpenAI GPT-4o-mini를 활용한 의미론적 분석과 PostgreSQL 데이터베이스의 기관 정보를 결합합니다.

## 주요 기능

- OpenAI GPT-4o-mini 기반 의미론적 분석
- PostgreSQL 읽기 전용 연결 (yeirin 메인 백엔드 DB 공유)
- RAG (Retrieval-Augmented Generation) 아키텍처
- 기관별 점수 및 추천 사유 제공

## 빠른 시작

```bash
# 의존성 설치
uv sync --all-extras

# 환경 변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY 설정

# 서버 실행
uv run uvicorn yeirin_ai.main:app --reload --port 8001
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/health` | 서비스 상태 확인 |
| POST | `/api/v1/recommendations` | 상담 기관 추천 요청 |

### 추천 요청 예시

```bash
curl -X POST http://localhost:8001/api/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{
    "counsel_request_text": "7세 아들이 ADHD 진단을 받았습니다. 학교에서 집중하지 못하고 친구들과 자주 다툽니다."
  }'
```

### 응답 예시

```json
{
  "recommendations": [
    {
      "institution_id": "uuid-here",
      "center_name": "서울아동심리상담센터",
      "score": 0.95,
      "reasoning": "ADHD 전문 상담사가 3명 있으며, 종합심리검사를 제공합니다.",
      "address": "서울시 강남구 테헤란로 123",
      "average_rating": 4.8
    }
  ],
  "total_institutions": 5,
  "request_text": "7세 아들이 ADHD 진단을 받았습니다..."
}
```

## 기술 스택

- **Framework**: FastAPI 0.115+
- **ORM**: SQLAlchemy 2.0 (비동기)
- **LLM**: OpenAI GPT-4o-mini
- **Database**: PostgreSQL 15 (읽기 전용)
- **Package Manager**: uv

## 프로젝트 구조

```
yeirin_ai/
├── api/                    # API 라우터
│   └── routes/
│       ├── health.py       # 헬스 체크
│       └── recommendations.py  # 추천 API
├── core/                   # 설정 및 공통
│   ├── config/
│   │   └── settings.py     # 환경 설정
│   └── models/
│       └── api.py          # API DTO
├── domain/                 # 도메인 모델
│   ├── institution/
│   │   └── models.py       # 기관 도메인
│   └── recommendation/
│       └── models.py       # 추천 도메인
├── infrastructure/         # 인프라 계층
│   ├── database/
│   │   ├── connection.py   # DB 연결
│   │   ├── models.py       # ORM 모델
│   │   └── repository.py   # 레포지토리
│   └── llm/
│       └── openai_client.py  # OpenAI 클라이언트
├── services/               # 애플리케이션 서비스
│   └── recommendation_service.py
└── main.py                 # 앱 진입점
```

## 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 | (필수) |
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql://yeirin:yeirin123@localhost:5433/yeirin_dev` |
| `DEBUG` | 디버그 모드 | `false` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |

## 테스트

```bash
# 전체 테스트 실행
uv run pytest

# 커버리지 리포트
uv run pytest --cov=yeirin_ai
```

## MSA 구성

이 서비스는 예이린 MSA의 일부입니다:
- **yeirin** (NestJS): 메인 백엔드 - 회원, 상담의뢰, 기관 관리
- **yeirin-ai** (FastAPI): AI 추천 서비스 (현재)
- **soul-e** (FastAPI): LLM 기반 심리상담 챗봇
