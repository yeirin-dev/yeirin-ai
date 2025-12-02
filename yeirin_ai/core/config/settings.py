"""pydantic-settings를 활용한 애플리케이션 설정."""

from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 환경 설정.

    환경 변수 또는 .env 파일에서 설정값을 로드합니다.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 애플리케이션 기본 설정
    app_name: str = Field(default="yeirin-ai", description="애플리케이션 이름")
    app_version: str = Field(default="0.1.0", description="애플리케이션 버전")
    debug: bool = Field(default=False, description="디버그 모드 활성화 여부")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="로깅 레벨"
    )

    # API 설정
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 경로 접두사")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], description="CORS 허용 오리진 목록"
    )

    # 데이터베이스 설정 (읽기 전용)
    database_url: PostgresDsn = Field(
        default="postgresql://yeirin:yeirin123@localhost:5433/yeirin_dev",
        description="PostgreSQL 연결 URL (읽기 전용)",
    )

    # OpenAI 설정
    openai_api_key: str = Field(description="OpenAI API 키")
    openai_model: str = Field(
        default="gpt-4o-mini", description="추천에 사용할 OpenAI 모델"
    )
    openai_temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="OpenAI temperature 파라미터"
    )
    openai_max_tokens: int = Field(
        default=2000, gt=0, description="OpenAI 응답 최대 토큰 수"
    )

    # 추천 서비스 설정
    max_recommendations: int = Field(
        default=5, ge=1, le=10, description="반환할 최대 추천 기관 수"
    )

    # Soul-E MSA 연동 설정
    soul_e_webhook_url: str | None = Field(
        default=None, description="Soul-E Webhook 콜백 URL"
    )

    # Yeirin 메인 백엔드 MSA 연동 설정
    yeirin_backend_url: str = Field(
        default="http://localhost:3000", description="Yeirin 메인 백엔드 URL"
    )
    internal_api_secret: str = Field(
        default="yeirin-internal-secret", description="내부 서비스 간 통신용 API 키"
    )


# 전역 설정 인스턴스
settings = Settings()
