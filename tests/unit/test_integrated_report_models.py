"""통합 보고서 도메인 모델 테스트.

BirthDate, GuardianInfo, InstitutionInfo 등 사회서비스 이용 추천서
관련 모델을 테스트합니다.
"""

import pytest
from pydantic import ValidationError

from yeirin_ai.domain.integrated_report.models import (
    BasicInfo,
    BirthDate,
    ChildInfo,
    CoverInfo,
    GuardianInfo,
    InstitutionInfo,
    IntegratedReportRequest,
    IntegratedReportResult,
    KprcSummary,
    PsychologicalInfo,
    RequestDate,
    RequestMotivation,
)


class TestBirthDate:
    """BirthDate 모델 테스트."""

    def test_올바른_생년월일로_객체를_생성한다(self) -> None:
        """올바른 생년월일로 BirthDate 객체를 생성할 수 있다."""
        # Given
        year, month, day = 2015, 3, 15

        # When
        birth_date = BirthDate(year=year, month=month, day=day)

        # Then
        assert birth_date.year == 2015
        assert birth_date.month == 3
        assert birth_date.day == 15

    def test_한국어_문자열로_변환한다(self) -> None:
        """생년월일을 한국어 문자열로 변환한다 (YYYY년 MM월 DD일 형식)."""
        # Given
        birth_date = BirthDate(year=2015, month=3, day=15)

        # When
        korean_string = birth_date.to_korean_string()

        # Then
        assert korean_string == "2015년 3월 15일"

    def test_월은_1에서_12_사이여야_한다(self) -> None:
        """월(month)은 1~12 범위여야 한다."""
        # When & Then: 유효하지 않은 월(13)
        with pytest.raises(ValidationError) as exc_info:
            BirthDate(year=2015, month=13, day=15)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("month",) for e in errors)

    def test_월은_0이_될_수_없다(self) -> None:
        """월(month)은 0이 될 수 없다."""
        with pytest.raises(ValidationError):
            BirthDate(year=2015, month=0, day=15)

    def test_일은_1에서_31_사이여야_한다(self) -> None:
        """일(day)은 1~31 범위여야 한다."""
        # When & Then: 유효하지 않은 일(32)
        with pytest.raises(ValidationError) as exc_info:
            BirthDate(year=2015, month=3, day=32)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("day",) for e in errors)

    def test_경계값_월_1월과_12월이_유효하다(self) -> None:
        """경계값인 1월과 12월이 유효하다."""
        # When
        january = BirthDate(year=2015, month=1, day=1)
        december = BirthDate(year=2015, month=12, day=31)

        # Then
        assert january.month == 1
        assert december.month == 12

    def test_한자리_월과_일도_올바르게_출력한다(self) -> None:
        """한 자리 월과 일도 패딩 없이 올바르게 출력한다."""
        # Given
        birth_date = BirthDate(year=2015, month=1, day=5)

        # When
        korean_string = birth_date.to_korean_string()

        # Then
        assert korean_string == "2015년 1월 5일"


class TestGuardianInfo:
    """GuardianInfo 모델 테스트."""

    def test_모든_필수_필드로_보호자_정보를_생성한다(self) -> None:
        """모든 필수 필드로 보호자 정보를 생성할 수 있다."""
        # Given & When
        guardian = GuardianInfo(
            name="홍부모",
            phoneNumber="010-1234-5678",
            address="서울시 강남구 테헤란로 123",
            relationToChild="부",
        )

        # Then
        assert guardian.name == "홍부모"
        assert guardian.phoneNumber == "010-1234-5678"
        assert guardian.address == "서울시 강남구 테헤란로 123"
        assert guardian.relationToChild == "부"

    def test_선택_필드가_기본값으로_None이다(self) -> None:
        """선택 필드(homePhone, addressDetail)가 기본값으로 None이다."""
        # Given & When
        guardian = GuardianInfo(
            name="홍부모",
            phoneNumber="010-1234-5678",
            address="서울시 강남구 테헤란로 123",
            relationToChild="부",
        )

        # Then
        assert guardian.homePhone is None
        assert guardian.addressDetail is None

    def test_모든_필드를_포함하여_생성한다(self) -> None:
        """선택 필드를 포함한 모든 필드로 생성할 수 있다."""
        # Given & When
        guardian = GuardianInfo(
            name="홍부모",
            phoneNumber="010-1234-5678",
            homePhone="02-123-4567",
            address="서울시 강남구 테헤란로 123",
            addressDetail="101동 1001호",
            relationToChild="모",
        )

        # Then
        assert guardian.homePhone == "02-123-4567"
        assert guardian.addressDetail == "101동 1001호"
        assert guardian.relationToChild == "모"

    def test_필수_필드가_없으면_에러가_발생한다(self) -> None:
        """필수 필드(name)가 없으면 ValidationError가 발생한다."""
        with pytest.raises(ValidationError) as exc_info:
            GuardianInfo(
                phoneNumber="010-1234-5678",
                address="서울시 강남구",
                relationToChild="부",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_다양한_관계_유형을_허용한다(self) -> None:
        """다양한 이용자와의 관계 유형을 허용한다."""
        relations = ["부", "모", "조부", "조모", "삼촌", "담임교사"]

        for relation in relations:
            # When
            guardian = GuardianInfo(
                name="보호자",
                phoneNumber="010-0000-0000",
                address="주소",
                relationToChild=relation,
            )

            # Then
            assert guardian.relationToChild == relation


class TestInstitutionInfo:
    """InstitutionInfo 모델 테스트."""

    def test_모든_필수_필드로_기관_정보를_생성한다(self) -> None:
        """모든 필수 필드로 기관/작성자 정보를 생성할 수 있다."""
        # Given & When
        institution = InstitutionInfo(
            institutionName="서울초등학교",
            phoneNumber="02-123-4567",
            address="서울시 강남구 학동로 456",
            writerPosition="담임교사",
            writerName="김선생",
            relationToChild="담임교사",
        )

        # Then
        assert institution.institutionName == "서울초등학교"
        assert institution.phoneNumber == "02-123-4567"
        assert institution.address == "서울시 강남구 학동로 456"
        assert institution.writerPosition == "담임교사"
        assert institution.writerName == "김선생"
        assert institution.relationToChild == "담임교사"

    def test_상세_주소가_선택_필드이다(self) -> None:
        """상세 주소(addressDetail)가 선택 필드이다."""
        # Given & When
        institution = InstitutionInfo(
            institutionName="서울초등학교",
            phoneNumber="02-123-4567",
            address="서울시 강남구 학동로 456",
            writerPosition="담임교사",
            writerName="김선생",
            relationToChild="담임교사",
        )

        # Then
        assert institution.addressDetail is None

    def test_상세_주소를_포함하여_생성한다(self) -> None:
        """상세 주소를 포함하여 생성할 수 있다."""
        # Given & When
        institution = InstitutionInfo(
            institutionName="서울초등학교",
            phoneNumber="02-123-4567",
            address="서울시 강남구 학동로 456",
            addressDetail="3층 교무실",
            writerPosition="담임교사",
            writerName="김선생",
            relationToChild="담임교사",
        )

        # Then
        assert institution.addressDetail == "3층 교무실"

    def test_필수_필드가_없으면_에러가_발생한다(self) -> None:
        """필수 필드(writerName)가 없으면 ValidationError가 발생한다."""
        with pytest.raises(ValidationError) as exc_info:
            InstitutionInfo(
                institutionName="서울초등학교",
                phoneNumber="02-123-4567",
                address="서울시 강남구",
                writerPosition="담임교사",
                # writerName 누락
                relationToChild="담임교사",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("writerName",) for e in errors)

    def test_다양한_직책_유형을_허용한다(self) -> None:
        """다양한 직 또는 자격 유형을 허용한다."""
        positions = ["담임교사", "사회복지사", "상담사", "특수교사", "교감", "원장"]

        for position in positions:
            # When
            institution = InstitutionInfo(
                institutionName="기관명",
                phoneNumber="02-000-0000",
                address="주소",
                writerPosition=position,
                writerName="작성자",
                relationToChild="관계",
            )

            # Then
            assert institution.writerPosition == position


class TestChildInfoWithBirthDate:
    """ChildInfo 모델의 birthDate 필드 테스트."""

    def test_생년월일_없이_아동_정보를_생성한다(self) -> None:
        """생년월일 없이도 아동 정보를 생성할 수 있다 (기존 호환성)."""
        # Given & When
        child = ChildInfo(
            name="홍길동",
            gender="MALE",
            age=10,
            grade="초4",
        )

        # Then
        assert child.birthDate is None

    def test_생년월일을_포함하여_아동_정보를_생성한다(self) -> None:
        """생년월일을 포함하여 아동 정보를 생성할 수 있다."""
        # Given
        birth_date = BirthDate(year=2015, month=3, day=15)

        # When
        child = ChildInfo(
            name="홍길동",
            gender="MALE",
            age=10,
            grade="초4",
            birthDate=birth_date,
        )

        # Then
        assert child.birthDate is not None
        assert child.birthDate.year == 2015
        assert child.birthDate.to_korean_string() == "2015년 3월 15일"


class TestIntegratedReportRequest:
    """IntegratedReportRequest 모델의 사회서비스 이용 추천서 필드 테스트."""

    @pytest.fixture
    def base_request_data(self) -> dict:
        """기본 요청 데이터 픽스처."""
        return {
            "counsel_request_id": "123e4567-e89b-12d3-a456-426614174000",
            "child_id": "123e4567-e89b-12d3-a456-426614174001",
            "child_name": "홍길동",
            "cover_info": {
                "requestDate": {"year": 2025, "month": 1, "day": 15},
                "centerName": "서울아동발달센터",
                "counselorName": "김상담",
            },
            "basic_info": {
                "childInfo": {
                    "name": "홍길동",
                    "gender": "MALE",
                    "age": 10,
                    "grade": "초4",
                },
                "careType": "PRIORITY",
            },
            "psychological_info": {
                "medicalHistory": "ADHD 진단 이력",
                "specialNotes": "학교 적응에 어려움",
            },
            "request_motivation": {
                "motivation": "행동 교정 필요",
                "goals": "감정 조절 능력 향상",
            },
            "kprc_summary": {
                "expertOpinion": "본 아동은 KPRC 검사 결과...",
            },
            "assessment_report_s3_key": "assessment-reports/KPRC_홍길동_abc123.pdf",
        }

    def test_사회서비스_추천서_정보_없이_요청을_생성한다(
        self, base_request_data: dict
    ) -> None:
        """guardian_info와 institution_info 없이 요청을 생성할 수 있다."""
        # When
        request = IntegratedReportRequest(**base_request_data)

        # Then
        assert request.guardian_info is None
        assert request.institution_info is None

    def test_보호자_정보만_포함하여_요청을_생성한다(
        self, base_request_data: dict
    ) -> None:
        """보호자 정보(guardian_info)만 포함하여 요청을 생성할 수 있다."""
        # Given
        base_request_data["guardian_info"] = {
            "name": "홍부모",
            "phoneNumber": "010-1234-5678",
            "address": "서울시 강남구 테헤란로 123",
            "relationToChild": "부",
        }

        # When
        request = IntegratedReportRequest(**base_request_data)

        # Then
        assert request.guardian_info is not None
        assert request.guardian_info.name == "홍부모"
        assert request.institution_info is None

    def test_기관_정보만_포함하여_요청을_생성한다(
        self, base_request_data: dict
    ) -> None:
        """기관 정보(institution_info)만 포함하여 요청을 생성할 수 있다."""
        # Given
        base_request_data["institution_info"] = {
            "institutionName": "서울초등학교",
            "phoneNumber": "02-123-4567",
            "address": "서울시 강남구 학동로 456",
            "writerPosition": "담임교사",
            "writerName": "김선생",
            "relationToChild": "담임교사",
        }

        # When
        request = IntegratedReportRequest(**base_request_data)

        # Then
        assert request.guardian_info is None
        assert request.institution_info is not None
        assert request.institution_info.institutionName == "서울초등학교"

    def test_보호자와_기관_정보를_모두_포함하여_요청을_생성한다(
        self, base_request_data: dict
    ) -> None:
        """보호자와 기관 정보를 모두 포함하여 요청을 생성할 수 있다."""
        # Given
        base_request_data["guardian_info"] = {
            "name": "홍부모",
            "phoneNumber": "010-1234-5678",
            "address": "서울시 강남구 테헤란로 123",
            "relationToChild": "부",
        }
        base_request_data["institution_info"] = {
            "institutionName": "서울초등학교",
            "phoneNumber": "02-123-4567",
            "address": "서울시 강남구 학동로 456",
            "writerPosition": "담임교사",
            "writerName": "김선생",
            "relationToChild": "담임교사",
        }

        # When
        request = IntegratedReportRequest(**base_request_data)

        # Then
        assert request.guardian_info is not None
        assert request.institution_info is not None
        assert request.guardian_info.name == "홍부모"
        assert request.institution_info.writerName == "김선생"

    def test_아동_생년월일을_포함하여_요청을_생성한다(
        self, base_request_data: dict
    ) -> None:
        """아동 생년월일을 포함하여 요청을 생성할 수 있다."""
        # Given
        base_request_data["basic_info"]["childInfo"]["birthDate"] = {
            "year": 2015,
            "month": 3,
            "day": 15,
        }

        # When
        request = IntegratedReportRequest(**base_request_data)

        # Then
        assert request.basic_info.childInfo.birthDate is not None
        assert request.basic_info.childInfo.birthDate.year == 2015
        assert request.basic_info.childInfo.birthDate.to_korean_string() == "2015년 3월 15일"


class TestIntegratedReportResult:
    """IntegratedReportResult 모델 테스트."""

    def test_성공_결과를_생성한다(self) -> None:
        """성공 상태의 결과를 생성할 수 있다."""
        # When
        result = IntegratedReportResult(
            counsel_request_id="123e4567-e89b-12d3-a456-426614174000",
            integrated_report_s3_key="integrated-reports/IR_홍길동_abc123_20250115.pdf",
            status="completed",
        )

        # Then
        assert result.status == "completed"
        assert result.integrated_report_s3_key is not None
        assert result.error_message is None

    def test_실패_결과를_생성한다(self) -> None:
        """실패 상태의 결과를 생성할 수 있다."""
        # When
        result = IntegratedReportResult(
            counsel_request_id="123e4567-e89b-12d3-a456-426614174000",
            integrated_report_s3_key=None,
            status="failed",
            error_message="템플릿 파일을 찾을 수 없습니다",
        )

        # Then
        assert result.status == "failed"
        assert result.integrated_report_s3_key is None
        assert result.error_message == "템플릿 파일을 찾을 수 없습니다"

    def test_상태는_completed_또는_failed만_허용한다(self) -> None:
        """상태(status)는 'completed' 또는 'failed'만 허용한다."""
        with pytest.raises(ValidationError):
            IntegratedReportResult(
                counsel_request_id="123e4567-e89b-12d3-a456-426614174000",
                status="pending",  # 허용되지 않는 상태
            )
