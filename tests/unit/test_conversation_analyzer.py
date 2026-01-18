"""대화 분석기 테스트.

ConversationAnalyzer의 Soul-E 대화 분석 로직을 테스트합니다.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yeirin_ai.infrastructure.external.soul_e_client import (
    ConversationHistory,
    ConversationMessage,
    ConversationSession,
)
from yeirin_ai.infrastructure.llm.conversation_analyzer import (
    ChildContext,
    ConversationAnalysis,
    ConversationAnalyzer,
)


class TestChildContext:
    """ChildContext 데이터 클래스 테스트."""

    def test_MALE_성별을_한국어로_변환한다(self) -> None:
        """MALE 성별이 '남'으로 변환된다."""
        # Given
        context = ChildContext(name="홍길동", gender="MALE")

        # When
        result = context.get_gender_korean()

        # Then
        assert result == "남"

    def test_FEMALE_성별을_한국어로_변환한다(self) -> None:
        """FEMALE 성별이 '여'로 변환된다."""
        # Given
        context = ChildContext(name="홍길순", gender="FEMALE")

        # When
        result = context.get_gender_korean()

        # Then
        assert result == "여"

    def test_성별_없으면_빈_문자열_반환한다(self) -> None:
        """성별이 None이면 빈 문자열을 반환한다."""
        # Given
        context = ChildContext(name="홍길동")

        # When
        result = context.get_gender_korean()

        # Then
        assert result == ""

    def test_상담_목표를_저장할_수_있다(self) -> None:
        """상담 목표를 저장할 수 있다."""
        # Given
        context = ChildContext(
            name="홍길동",
            age=10,
            goals="감정 조절 능력 향상",
        )

        # Then
        assert context.goals == "감정 조절 능력 향상"


class TestConversationAnalysis:
    """ConversationAnalysis 데이터 클래스 테스트."""

    def test_기본값으로_초기화된다(self) -> None:
        """기본값으로 초기화된다."""
        # When
        analysis = ConversationAnalysis()

        # Then
        assert analysis.summary_lines == []
        assert analysis.expert_analysis == ""
        assert analysis.key_observations == []
        assert analysis.emotional_keywords == []
        assert analysis.recommended_focus_areas == []
        assert analysis.confidence_score == 0.0
        assert analysis.session_count == 0
        assert analysis.message_count == 0

    def test_모든_필드를_초기화할_수_있다(self) -> None:
        """모든 필드를 초기화할 수 있다."""
        # When
        analysis = ConversationAnalysis(
            summary_lines=["줄1", "줄2", "줄3"],
            expert_analysis="전문가 분석",
            key_observations=["관찰1", "관찰2"],
            emotional_keywords=["불안", "스트레스"],
            recommended_focus_areas=["정서 조절", "또래 관계"],
            confidence_score=0.85,
            session_count=3,
            message_count=25,
        )

        # Then
        assert len(analysis.summary_lines) == 3
        assert analysis.expert_analysis == "전문가 분석"
        assert len(analysis.key_observations) == 2
        assert "불안" in analysis.emotional_keywords
        assert analysis.session_count == 3


class TestConversationAnalyzerInitialization:
    """ConversationAnalyzer 초기화 테스트."""

    def test_필요한_의존성을_초기화한다(self) -> None:
        """OpenAI 클라이언트와 Soul-E 클라이언트를 초기화한다."""
        # Given
        with patch(
            "yeirin_ai.infrastructure.llm.conversation_analyzer.settings"
        ) as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o-mini"

            with patch(
                "yeirin_ai.infrastructure.llm.conversation_analyzer.SoulEClient"
            ) as mock_soul_e:
                # When
                analyzer = ConversationAnalyzer()

        # Then
        assert analyzer.client is not None
        assert analyzer.soul_e_client is not None
        assert analyzer.model == "gpt-4o-mini"


class TestConversationAnalyzerPromptBuilding:
    """프롬프트 생성 테스트."""

    @pytest.fixture
    def analyzer(self) -> ConversationAnalyzer:
        """테스트용 분석기 인스턴스."""
        with patch(
            "yeirin_ai.infrastructure.llm.conversation_analyzer.settings"
        ) as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o-mini"

            with patch(
                "yeirin_ai.infrastructure.llm.conversation_analyzer.SoulEClient"
            ):
                return ConversationAnalyzer()

    def test_프롬프트에_아동_정보가_포함된다(
        self, analyzer: ConversationAnalyzer
    ) -> None:
        """프롬프트에 아동 정보가 포함된다."""
        # Given
        child_context = ChildContext(
            name="홍길동",
            age=10,
            gender="MALE",
            goals="감정 조절 능력 향상",
        )
        conversation_text = "[2025-01-05 10:00] 아동: 안녕하세요"

        # When
        prompt = analyzer._build_prompt(conversation_text, child_context)

        # Then
        assert "홍길동" in prompt
        assert "10세" in prompt
        assert "남" in prompt
        assert "감정 조절 능력 향상" in prompt

    def test_프롬프트에_대화내역이_포함된다(
        self, analyzer: ConversationAnalyzer
    ) -> None:
        """프롬프트에 대화내역이 포함된다."""
        # Given
        child_context = ChildContext(name="홍길동")
        conversation_text = "[2025-01-05] 아동: 학교에서 힘들어요"

        # When
        prompt = analyzer._build_prompt(conversation_text, child_context)

        # Then
        assert "학교에서 힘들어요" in prompt
        assert "소울이(AI 상담사)와의 대화내역" in prompt

    def test_시스템_프롬프트에_분석_원칙이_포함된다(
        self, analyzer: ConversationAnalyzer
    ) -> None:
        """시스템 프롬프트에 분석 원칙이 포함된다."""
        # When
        system_prompt = analyzer._get_system_prompt()

        # Then
        assert "소울이" in system_prompt
        assert "강점 우선" in system_prompt
        assert "진단 금지" in system_prompt
        assert "정서 상태" in system_prompt


class TestConversationAnalyzerAnalysis:
    """대화 분석 테스트."""

    @pytest.fixture
    def analyzer(self) -> ConversationAnalyzer:
        """테스트용 분석기 인스턴스."""
        with patch(
            "yeirin_ai.infrastructure.llm.conversation_analyzer.settings"
        ) as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o-mini"

            with patch(
                "yeirin_ai.infrastructure.llm.conversation_analyzer.SoulEClient"
            ):
                return ConversationAnalyzer()

    @pytest.fixture
    def sample_history(self) -> ConversationHistory:
        """샘플 대화내역."""
        now = datetime.now(timezone.utc)
        return ConversationHistory(
            child_id="child-123",
            sessions=[
                ConversationSession(
                    id="session-1",
                    status="closed",
                    message_count=5,
                    created_at=now,
                    updated_at=now,
                )
            ],
            messages=[
                ConversationMessage(
                    id="msg-1",
                    role="user",
                    content="안녕하세요, 소울이",
                    created_at=now,
                ),
                ConversationMessage(
                    id="msg-2",
                    role="assistant",
                    content="안녕! 오늘 기분이 어때?",
                    created_at=now,
                ),
                ConversationMessage(
                    id="msg-3",
                    role="user",
                    content="학교에서 친구들이랑 잘 안 맞아요",
                    created_at=now,
                ),
            ],
            total_sessions=1,
            total_messages=3,
        )

    @pytest.fixture
    def sample_child_context(self) -> ChildContext:
        """샘플 아동 컨텍스트."""
        return ChildContext(
            name="홍길동",
            age=10,
            gender="MALE",
        )

    def test_기본_분석을_생성한다(
        self,
        analyzer: ConversationAnalyzer,
        sample_child_context: ChildContext,
    ) -> None:
        """대화내역이 없거나 분석 실패 시 기본 분석을 생성한다."""
        # When
        result = analyzer._create_default_analysis(sample_child_context)

        # Then
        assert isinstance(result, ConversationAnalysis)
        assert len(result.summary_lines) == 3
        assert "홍길동" in result.expert_analysis
        assert result.confidence_score == 0.4

    def test_분석_결과를_파싱한다(
        self,
        analyzer: ConversationAnalyzer,
        sample_history: ConversationHistory,
    ) -> None:
        """OpenAI 응답을 ConversationAnalysis로 파싱한다."""
        # Given
        result = {
            "summary_lines": ["줄1", "줄2", "줄3"],
            "expert_analysis": "전문가 종합 분석",
            "key_observations": ["관찰1", "관찰2"],
            "emotional_keywords": ["또래갈등", "학교 스트레스"],
            "recommended_focus_areas": ["또래 관계 향상", "사회성 발달"],
            "confidence_score": 0.85,
        }

        # When
        analysis = analyzer._parse_analysis(result, sample_history)

        # Then
        assert len(analysis.summary_lines) == 3
        assert analysis.expert_analysis == "전문가 종합 분석"
        assert "또래갈등" in analysis.emotional_keywords
        assert analysis.confidence_score == 0.85
        assert analysis.session_count == 1
        assert analysis.message_count == 3

    @pytest.mark.asyncio
    async def test_대화내역으로_분석을_수행한다(
        self,
        analyzer: ConversationAnalyzer,
        sample_history: ConversationHistory,
        sample_child_context: ChildContext,
    ) -> None:
        """대화내역으로 분석을 수행한다."""
        # Given
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"summary_lines": ["긍정적 특성", "관심 영역", "기대 성장"], '
                    '"expert_analysis": "전문가 분석입니다.", '
                    '"key_observations": ["관찰1", "관찰2"], '
                    '"emotional_keywords": ["또래갈등"], '
                    '"recommended_focus_areas": ["또래 관계"], '
                    '"confidence_score": 0.8}'
                )
            )
        ]

        # soul_e_client.format_conversation_for_analysis 모킹
        analyzer.soul_e_client.format_conversation_for_analysis = MagicMock(
            return_value="[대화내역]"
        )

        with patch.object(
            analyzer.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            # When
            result = await analyzer.analyze_conversation(
                sample_history,
                sample_child_context,
            )

        # Then
        assert isinstance(result, ConversationAnalysis)
        assert len(result.summary_lines) == 3
        assert result.confidence_score == 0.8

    @pytest.mark.asyncio
    async def test_API_실패시_기본_분석을_반환한다(
        self,
        analyzer: ConversationAnalyzer,
        sample_history: ConversationHistory,
        sample_child_context: ChildContext,
    ) -> None:
        """OpenAI API 실패시 기본 분석으로 폴백한다."""
        # Given
        analyzer.soul_e_client.format_conversation_for_analysis = MagicMock(
            return_value="[대화내역]"
        )

        with patch.object(
            analyzer.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            # When
            result = await analyzer.analyze_conversation(
                sample_history,
                sample_child_context,
            )

        # Then
        assert isinstance(result, ConversationAnalysis)
        assert result.confidence_score == 0.4  # 기본 신뢰도

    @pytest.mark.asyncio
    async def test_child_id로_대화내역을_조회하고_분석한다(
        self,
        analyzer: ConversationAnalyzer,
        sample_history: ConversationHistory,
        sample_child_context: ChildContext,
    ) -> None:
        """child_id로 Soul-E에서 대화내역을 조회하고 분석한다."""
        # Given
        # Soul-E 클라이언트 모킹
        analyzer.soul_e_client.get_conversation_history = AsyncMock(
            return_value=sample_history
        )
        analyzer.soul_e_client.format_conversation_for_analysis = MagicMock(
            return_value="[대화내역]"
        )

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"summary_lines": ["줄1", "줄2", "줄3"], '
                    '"expert_analysis": "분석", '
                    '"key_observations": [], '
                    '"emotional_keywords": [], '
                    '"recommended_focus_areas": [], '
                    '"confidence_score": 0.9}'
                )
            )
        ]

        with patch.object(
            analyzer.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            # When
            result = await analyzer.analyze_from_child_id(
                "child-123",
                sample_child_context,
            )

        # Then
        assert isinstance(result, ConversationAnalysis)
        assert result.confidence_score == 0.9
        analyzer.soul_e_client.get_conversation_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_대화내역_없으면_기본_분석을_반환한다(
        self,
        analyzer: ConversationAnalyzer,
        sample_child_context: ChildContext,
    ) -> None:
        """대화내역이 없으면 기본 분석을 반환한다."""
        # Given
        empty_history = ConversationHistory(
            child_id="child-123",
            sessions=[],
            messages=[],
            total_sessions=0,
            total_messages=0,
        )
        analyzer.soul_e_client.get_conversation_history = AsyncMock(
            return_value=empty_history
        )

        # When
        result = await analyzer.analyze_from_child_id(
            "child-123",
            sample_child_context,
        )

        # Then
        assert isinstance(result, ConversationAnalysis)
        assert result.confidence_score == 0.4  # 기본 분석 신뢰도

    @pytest.mark.asyncio
    async def test_Soul_E_API_실패시_기본_분석을_반환한다(
        self,
        analyzer: ConversationAnalyzer,
        sample_child_context: ChildContext,
    ) -> None:
        """Soul-E API 호출 실패시 기본 분석으로 폴백한다."""
        # Given
        analyzer.soul_e_client.get_conversation_history = AsyncMock(
            side_effect=Exception("Soul-E API Error")
        )

        # When
        result = await analyzer.analyze_from_child_id(
            "child-123",
            sample_child_context,
        )

        # Then
        assert isinstance(result, ConversationAnalysis)
        assert result.confidence_score == 0.4


class TestSoulEClientFormatting:
    """Soul-E 대화내역 포맷팅 테스트."""

    @pytest.fixture
    def sample_history(self) -> ConversationHistory:
        """샘플 대화내역."""
        now = datetime.now(timezone.utc)
        return ConversationHistory(
            child_id="child-123",
            sessions=[],
            messages=[
                ConversationMessage(
                    id="msg-1",
                    role="user",
                    content="안녕하세요",
                    created_at=now,
                ),
                ConversationMessage(
                    id="msg-2",
                    role="assistant",
                    content="안녕! 오늘 기분이 어때?",
                    created_at=now,
                ),
            ],
            total_sessions=0,
            total_messages=2,
        )

    def test_대화내역을_분석용_텍스트로_포맷한다(
        self, sample_history: ConversationHistory
    ) -> None:
        """대화내역을 분석용 텍스트로 포맷한다."""
        # Given
        with patch(
            "yeirin_ai.infrastructure.external.soul_e_client.settings"
        ) as mock_settings:
            mock_settings.soul_e_api_url = "http://localhost:8000"
            mock_settings.internal_api_secret = "test-secret"

            from yeirin_ai.infrastructure.external.soul_e_client import SoulEClient

            client = SoulEClient()

        # When
        result = client.format_conversation_for_analysis(sample_history)

        # Then
        assert "아동: 안녕하세요" in result
        assert "상담사(소울이): 안녕! 오늘 기분이 어때?" in result

    def test_빈_대화내역은_빈_문자열을_반환한다(self) -> None:
        """빈 대화내역은 빈 문자열을 반환한다."""
        # Given
        with patch(
            "yeirin_ai.infrastructure.external.soul_e_client.settings"
        ) as mock_settings:
            mock_settings.soul_e_api_url = "http://localhost:8000"
            mock_settings.internal_api_secret = "test-secret"

            from yeirin_ai.infrastructure.external.soul_e_client import SoulEClient

            client = SoulEClient()

        empty_history = ConversationHistory(
            child_id="child-123",
            sessions=[],
            messages=[],
            total_sessions=0,
            total_messages=0,
        )

        # When
        result = client.format_conversation_for_analysis(empty_history)

        # Then
        assert result == ""
