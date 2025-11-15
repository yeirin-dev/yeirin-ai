"""Institution repository for database access."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yeirin_ai.domain.institution.models import Institution
from yeirin_ai.infrastructure.database.models import VoucherInstitutionORM


class InstitutionRepository:
    """바우처 기관 레포지토리 (읽기 전용)."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            session: Database session
        """
        self.session = session

    async def get_all(self) -> list[Institution]:
        """
        Get all institutions.

        Returns:
            List of all institutions
        """
        result = await self.session.execute(select(VoucherInstitutionORM))
        orm_institutions = result.scalars().all()

        return [self._to_domain(orm_inst) for orm_inst in orm_institutions]

    async def get_by_id(self, institution_id: str) -> Institution | None:
        """
        Get institution by ID.

        Args:
            institution_id: Institution UUID

        Returns:
            Institution if found, None otherwise
        """
        result = await self.session.execute(
            select(VoucherInstitutionORM).where(VoucherInstitutionORM.id == institution_id)
        )
        orm_institution = result.scalar_one_or_none()

        return self._to_domain(orm_institution) if orm_institution else None

    def _to_domain(self, orm_inst: VoucherInstitutionORM) -> Institution:
        """
        Convert ORM model to domain model.

        Args:
            orm_inst: ORM institution

        Returns:
            Domain institution
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
