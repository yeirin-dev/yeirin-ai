"""기관 도메인 모델.

바우처 상담 기관과 관련된 핵심 도메인 모델 및 열거형을 정의합니다.
"""

from datetime import date
from enum import Enum
from typing import Any


class VoucherType(str, Enum):
    """바우처 유형.

    정부 지원 바우처 프로그램 종류를 정의합니다.
    """

    DEVELOPMENTAL_REHABILITATION = "DEVELOPMENTAL_REHABILITATION"  # 발달재활
    LANGUAGE_DEVELOPMENT = "LANGUAGE_DEVELOPMENT"  # 언어발달
    CHILD_PSYCHOLOGY = "CHILD_PSYCHOLOGY"  # 아동심리
    PARENT_COUNSELING = "PARENT_COUNSELING"  # 부모상담
    OTHER = "OTHER"  # 기타


class ServiceType(str, Enum):
    """서비스 유형.

    상담 기관에서 제공하는 서비스 종류를 정의합니다.
    """

    COUNSELING = "COUNSELING"  # 일반 상담
    ART_THERAPY = "ART_THERAPY"  # 미술치료
    MUSIC_THERAPY = "MUSIC_THERAPY"  # 음악치료
    PLAY_THERAPY = "PLAY_THERAPY"  # 놀이치료
    SENSORY_INTEGRATION = "SENSORY_INTEGRATION"  # 감각통합
    COGNITIVE_THERAPY = "COGNITIVE_THERAPY"  # 인지치료
    OTHER = "OTHER"  # 기타


class SpecialTreatment(str, Enum):
    """특수 치료 유형.

    전문 특수 치료 종류를 정의합니다.
    """

    LANGUAGE = "LANGUAGE"  # 언어치료
    DEVELOPMENTAL_REHABILITATION = "DEVELOPMENTAL_REHABILITATION"  # 발달재활치료
    OTHER = "OTHER"  # 기타
    NONE = "NONE"  # 없음


class Institution:
    """바우처 상담 기관 도메인 모델.

    상담 기관의 모든 정보를 캡슐화합니다.
    AI 추천 시스템에서 기관 특성을 분석하는 데 사용됩니다.
    """

    def __init__(
        self,
        id: str,
        center_name: str,
        representative_name: str,
        address: str,
        established_date: date,
        operating_vouchers: list[VoucherType],
        is_quality_certified: bool,
        max_capacity: int,
        introduction: str,
        counselor_count: int,
        counselor_certifications: list[str],
        primary_target_group: str,
        secondary_target_group: str | None,
        can_provide_comprehensive_test: bool,
        provided_services: list[ServiceType],
        special_treatments: list[SpecialTreatment],
        can_provide_parent_counseling: bool,
        average_rating: float,
        review_count: int,
    ) -> None:
        """기관을 초기화합니다.

        Args:
            id: 기관 UUID
            center_name: 센터명
            representative_name: 대표자명
            address: 기관 주소
            established_date: 설립일
            operating_vouchers: 운영 중인 바우처 목록
            is_quality_certified: 품질 인증 여부
            max_capacity: 최대 수용 인원
            introduction: 기관 소개
            counselor_count: 상담사 수
            counselor_certifications: 상담사 자격증 목록
            primary_target_group: 주요 대상군
            secondary_target_group: 부차 대상군
            can_provide_comprehensive_test: 종합심리검사 제공 가능 여부
            provided_services: 제공 서비스 목록
            special_treatments: 특수 치료 목록
            can_provide_parent_counseling: 부모 상담 제공 가능 여부
            average_rating: 평균 별점 (5점 만점)
            review_count: 리뷰 수
        """
        self.id = id
        self.center_name = center_name
        self.representative_name = representative_name
        self.address = address
        self.established_date = established_date
        self.operating_vouchers = operating_vouchers
        self.is_quality_certified = is_quality_certified
        self.max_capacity = max_capacity
        self.introduction = introduction
        self.counselor_count = counselor_count
        self.counselor_certifications = counselor_certifications
        self.primary_target_group = primary_target_group
        self.secondary_target_group = secondary_target_group
        self.can_provide_comprehensive_test = can_provide_comprehensive_test
        self.provided_services = provided_services
        self.special_treatments = special_treatments
        self.can_provide_parent_counseling = can_provide_parent_counseling
        self.average_rating = average_rating
        self.review_count = review_count

    def to_dict(self) -> dict[str, Any]:
        """LLM 컨텍스트용 딕셔너리로 변환합니다.

        Returns:
            기관 정보 딕셔너리
        """
        return {
            "id": self.id,
            "center_name": self.center_name,
            "address": self.address,
            "introduction": self.introduction,
            "operating_vouchers": [v.value for v in self.operating_vouchers],
            "is_quality_certified": self.is_quality_certified,
            "counselor_count": self.counselor_count,
            "counselor_certifications": self.counselor_certifications,
            "primary_target_group": self.primary_target_group,
            "secondary_target_group": self.secondary_target_group,
            "can_provide_comprehensive_test": self.can_provide_comprehensive_test,
            "provided_services": [s.value for s in self.provided_services],
            "special_treatments": [t.value for t in self.special_treatments],
            "can_provide_parent_counseling": self.can_provide_parent_counseling,
            "average_rating": self.average_rating,
            "review_count": self.review_count,
        }

    def __repr__(self) -> str:
        """문자열 표현을 반환합니다."""
        return f"<Institution id={self.id} name={self.center_name}>"
