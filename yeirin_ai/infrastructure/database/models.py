"""Database ORM models (read-only)."""

from datetime import date

from sqlalchemy import ARRAY, Boolean, Column, Date, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import DeclarativeBase

from yeirin_ai.domain.institution.models import ServiceType, SpecialTreatment, VoucherType


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class VoucherInstitutionORM(Base):
    """바우처 기관 ORM 모델 (읽기 전용)."""

    __tablename__ = "voucher_institutions"

    id = Column(UUID(as_uuid=False), primary_key=True)
    centerName = Column("centerName", String(100), nullable=False)
    representativeName = Column("representativeName", String(50), nullable=False)
    address = Column(String(200), nullable=False)
    establishedDate = Column("establishedDate", Date, nullable=False)
    operatingVouchers = Column(
        "operatingVouchers",
        ARRAY(ENUM(VoucherType, name="vouchertype_enum", create_type=False)),
        nullable=False,
    )
    isQualityCertified = Column("isQualityCertified", Boolean, default=False)
    maxCapacity = Column("maxCapacity", Integer, nullable=False)
    introduction = Column(String(200), nullable=False)
    counselorCount = Column("counselorCount", Integer, default=0)
    counselorCertifications = Column("counselorCertifications", ARRAY(Text), nullable=True)
    primaryTargetGroup = Column("primaryTargetGroup", String(50), nullable=False)
    secondaryTargetGroup = Column("secondaryTargetGroup", String(50), nullable=True)
    canProvideComprehensiveTest = Column(
        "canProvideComprehensiveTest", Boolean, default=False
    )
    providedServices = Column(
        "providedServices",
        ARRAY(ENUM(ServiceType, name="servicetype_enum", create_type=False)),
        nullable=False,
    )
    specialTreatments = Column(
        "specialTreatments",
        ARRAY(ENUM(SpecialTreatment, name="specialtreatment_enum", create_type=False)),
        nullable=False,
    )
    canProvideParentCounseling = Column("canProvideParentCounseling", Boolean, default=False)
    averageRating = Column("averageRating", Numeric(3, 2), default=0)
    reviewCount = Column("reviewCount", Integer, default=0)
    createdAt = Column("createdAt", Date, nullable=False)
    updatedAt = Column("updatedAt", Date, nullable=False)
