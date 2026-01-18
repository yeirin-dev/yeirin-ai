"""FastAPI 애플리케이션 진입점."""

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

# 로깅 설정 (모든 로거가 stdout으로 출력되도록)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,  # 기존 핸들러 덮어쓰기
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from yeirin_ai.api.routes import documents, health, integrated_reports, kprc, recommendations
from yeirin_ai.core.config.settings import settings
from yeirin_ai.infrastructure.database.connection import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    애플리케이션 생명주기 관리자.

    시작 시 데이터베이스 연결을 확인하고,
    종료 시 연결을 정리합니다.

    Args:
        app: FastAPI 애플리케이션 인스턴스
    """
    # 시작: 데이터베이스 연결 테스트
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    print("✅ 데이터베이스 연결 성공")

    yield

    # 종료: 리소스 정리
    await engine.dispose()
    print("👋 데이터베이스 연결 종료")


# FastAPI 애플리케이션 생성
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Yeirin AI 추천 서비스 - RAG 기반 상담 기관 매칭",
    lifespan=lifespan,
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(recommendations.router, prefix=settings.api_v1_prefix)
app.include_router(documents.router, prefix=settings.api_v1_prefix)
app.include_router(integrated_reports.router, prefix=settings.api_v1_prefix)
app.include_router(kprc.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    """루트 엔드포인트 - 서비스 정보 반환."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
