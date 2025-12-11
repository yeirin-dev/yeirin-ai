"""기관 레포지토리 - 데이터베이스 접근 계층."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yeirin_ai.domain.institution.models import Institution
from yeirin_ai.infrastructure.database.models import VoucherInstitutionORM


class InstitutionRepository:
    """바우처 기관 레포지토리 (읽기 전용).

    yeirin 메인 백엔드의 voucher_institutions 테이블에서
    기관 정보를 조회합니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        """레포지토리를 초기화합니다.

        Args:
            session: 비동기 데이터베이스 세션
        """
        self.session = session

    async def get_all(self) -> list[Institution]:
        """모든 기관을 조회합니다.

        Returns:
            전체 기관 도메인 모델 목록
        """
        result = await self.session.execute(select(VoucherInstitutionORM))
        orm_institutions = result.scalars().all()

        return [self._to_domain(orm_inst) for orm_inst in orm_institutions]

    async def get_by_id(self, institution_id: str) -> Institution | None:
        """ID로 기관을 조회합니다.

        Args:
            institution_id: 기관 UUID

        Returns:
            기관이 존재하면 도메인 모델, 없으면 None
        """
        result = await self.session.execute(
            select(VoucherInstitutionORM).where(VoucherInstitutionORM.id == institution_id)
        )
        orm_institution = result.scalar_one_or_none()

        return self._to_domain(orm_institution) if orm_institution else None

    def _to_domain(self, orm_inst: VoucherInstitutionORM) -> Institution:
        """ORM 모델을 도메인 모델로 변환합니다.

        Args:
            orm_inst: ORM 기관 엔티티

        Returns:
            기관 도메인 모델
        """
        return Institution(
            id=str(orm_inst.id),
            center_name=orm_inst.centerName,
            representative_name=orm_inst.representativeName,
            address=orm_inst.address,
            established_date=orm_inst.establishedDate,
            operating_vouchers=list(orm_inst.operatingVouchers),
            is_quality_certified=orm_inst.isQualityCertified,
            max_capacity=orm_inst.maxCapacity,
            introduction=orm_inst.introduction,
            counselor_count=orm_inst.counselorCount,
            counselor_certifications=list(orm_inst.counselorCertifications or []),
            primary_target_group=orm_inst.primaryTargetGroup,
            secondary_target_group=orm_inst.secondaryTargetGroup,
            can_provide_comprehensive_test=orm_inst.canProvideComprehensiveTest,
            provided_services=list(orm_inst.providedServices),
            special_treatments=list(orm_inst.specialTreatments),
            can_provide_parent_counseling=orm_inst.canProvideParentCounseling,
            average_rating=float(orm_inst.averageRating),
            review_count=orm_inst.reviewCount,
        )
