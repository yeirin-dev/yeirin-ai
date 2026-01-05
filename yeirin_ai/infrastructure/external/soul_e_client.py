"""Soul-E API 클라이언트 - 대화내역 조회.

Soul-E의 Internal API를 호출하여 아동의 대화내역을 조회합니다.
"""

import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel

from yeirin_ai.core.config.settings import settings

logger = logging.getLogger(__name__)


class SoulEClientError(Exception):
    """Soul-E 클라이언트 에러."""

    pass


class ConversationMessage(BaseModel):
    """대화 메시지."""

    id: str
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime
    metadata: dict[str, Any] | None = None


class ConversationSession(BaseModel):
    """대화 세션."""

    id: str
    user_id: str | None = None
    title: str | None = None
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] | None = None


class ConversationHistory(BaseModel):
    """대화 내역 응답."""

    child_id: str
    sessions: list[ConversationSession]
    messages: list[ConversationMessage]
    total_sessions: int
    total_messages: int


class SoulEClient:
    """Soul-E API 클라이언트.

    Soul-E Internal API를 호출하여 아동의 대화내역을 조회합니다.
    """

    def __init__(
        self,
        base_url: str | None = None,
        internal_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """클라이언트 초기화.

        Args:
            base_url: Soul-E API URL. None이면 설정에서 가져옴.
            internal_secret: Internal API Secret. None이면 설정에서 가져옴.
            timeout: HTTP 요청 타임아웃 (초).
        """
        self.base_url = (base_url or settings.soul_e_api_url).rstrip("/")
        self.internal_secret = internal_secret or settings.internal_api_secret
        self.timeout = timeout

    async def get_conversation_history(
        self,
        child_id: str,
        max_messages: int = 100,
        include_metadata: bool = False,
    ) -> ConversationHistory:
        """아동의 대화내역을 조회합니다.

        Args:
            child_id: 아동 ID (UUID)
            max_messages: 최대 메시지 수 (기본값: 100)
            include_metadata: 메타데이터 포함 여부

        Returns:
            ConversationHistory 객체

        Raises:
            SoulEClientError: API 호출 실패 시
        """
        url = f"{self.base_url}/api/v1/internal/conversations/{child_id}"
        params = {
            "max_messages": max_messages,
            "include_metadata": include_metadata,
        }
        headers = {
            "X-Internal-Secret": self.internal_secret,
            "Content-Type": "application/json",
        }

        logger.info(
            "Soul-E 대화내역 조회 요청",
            extra={"child_id": child_id, "url": url},
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 404:
                    logger.info(
                        "Soul-E 대화내역 없음",
                        extra={"child_id": child_id},
                    )
                    # 대화내역이 없는 경우 빈 결과 반환
                    return ConversationHistory(
                        child_id=child_id,
                        sessions=[],
                        messages=[],
                        total_sessions=0,
                        total_messages=0,
                    )

                if response.status_code == 401:
                    logger.error(
                        "Soul-E API 인증 실패",
                        extra={"child_id": child_id, "status_code": response.status_code},
                    )
                    raise SoulEClientError("Soul-E API 인증 실패: Internal API Secret 확인 필요")

                response.raise_for_status()

                data = response.json()
                history = ConversationHistory(
                    child_id=data["child_id"],
                    sessions=[
                        ConversationSession(
                            id=str(s["id"]),
                            user_id=s.get("user_id"),
                            title=s.get("title"),
                            status=s["status"],
                            message_count=s["message_count"],
                            created_at=datetime.fromisoformat(
                                s["created_at"].replace("Z", "+00:00")
                            ),
                            updated_at=datetime.fromisoformat(
                                s["updated_at"].replace("Z", "+00:00")
                            ),
                            metadata=s.get("metadata"),
                        )
                        for s in data.get("sessions", [])
                    ],
                    messages=[
                        ConversationMessage(
                            id=str(m["id"]),
                            role=m["role"],
                            content=m["content"],
                            created_at=datetime.fromisoformat(
                                m["created_at"].replace("Z", "+00:00")
                            ),
                            metadata=m.get("metadata"),
                        )
                        for m in data.get("messages", [])
                    ],
                    total_sessions=data.get("total_sessions", 0),
                    total_messages=data.get("total_messages", 0),
                )

                logger.info(
                    "Soul-E 대화내역 조회 성공",
                    extra={
                        "child_id": child_id,
                        "sessions_count": history.total_sessions,
                        "messages_count": history.total_messages,
                    },
                )

                return history

        except httpx.HTTPStatusError as e:
            logger.error(
                "Soul-E API HTTP 에러",
                extra={
                    "child_id": child_id,
                    "status_code": e.response.status_code,
                    "response": e.response.text[:500],
                },
            )
            raise SoulEClientError(f"Soul-E API 호출 실패: {e.response.status_code}") from e

        except httpx.RequestError as e:
            logger.error(
                "Soul-E API 연결 에러",
                extra={"child_id": child_id, "error": str(e)},
            )
            raise SoulEClientError(f"Soul-E API 연결 실패: {e}") from e

        except Exception as e:
            logger.error(
                "Soul-E 클라이언트 에러",
                extra={"child_id": child_id, "error": str(e)},
            )
            raise SoulEClientError(f"Soul-E 클라이언트 에러: {e}") from e

    def format_conversation_for_analysis(
        self,
        history: ConversationHistory,
        max_chars: int = 8000,
    ) -> str:
        """대화내역을 분석용 텍스트로 포맷합니다.

        Args:
            history: 대화내역
            max_chars: 최대 문자 수 (토큰 제한 고려)

        Returns:
            포맷된 대화내역 텍스트
        """
        if not history.messages:
            return ""

        formatted_parts = []

        for msg in history.messages:
            role_label = "아동" if msg.role == "user" else "상담사(소울이)"
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            formatted_parts.append(f"[{timestamp}] {role_label}: {msg.content}")

        full_text = "\n".join(formatted_parts)

        # 최대 문자 수 제한 (끝에서부터 자르기 - 최근 대화가 더 중요)
        if len(full_text) > max_chars:
            full_text = "...(이전 대화 생략)...\n" + full_text[-max_chars:]

        return full_text
