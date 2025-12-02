"""데이터베이스 연결 관리.

yeirin 메인 백엔드 PostgreSQL에 읽기 전용으로 연결합니다.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from yeirin_ai.core.config.settings import settings

# 비동기 엔진 생성 (읽기 전용)
engine: AsyncEngine = create_async_engine(
    str(settings.database_url).replace("postgresql://", "postgresql+psycopg://"),
    echo=settings.debug,  # 디버그 모드에서만 SQL 출력
    pool_pre_ping=True,  # 연결 상태 사전 확인
    pool_size=5,  # 커넥션 풀 크기
    max_overflow=10,  # 최대 오버플로우 연결 수
)

# 비동기 세션 팩토리 생성
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """비동기 데이터베이스 세션 의존성.

    FastAPI의 Depends를 통해 주입되며, 요청 종료 시 자동으로 세션을 닫습니다.

    Yields:
        비동기 데이터베이스 세션
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
