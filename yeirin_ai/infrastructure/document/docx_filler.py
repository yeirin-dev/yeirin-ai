"""DOCX 템플릿 채우기.

counsel_request_format.doc 템플릿을 상담의뢰지 데이터로 채웁니다.
"""

import io
import logging
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from yeirin_ai.domain.integrated_report.models import IntegratedReportRequest

logger = logging.getLogger(__name__)

# 템플릿 파일 경로
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "counsel_request_format.doc"


class DocxFillerError(Exception):
    """DOCX 채우기 에러."""

    pass


class CounselRequestDocxFiller:
    """상담의뢰지 DOCX 템플릿 채우기.

    counsel_request_format.doc 템플릿의 테이블 구조:
    - 테이블 1: 기본 정보 (이름, 성별, 연령, 학년, 센터이용기준)
    - 테이블 2: 정서심리 정보 (병력, 특이사항)
    - 테이블 3: 의뢰 정보 (의뢰동기, 목표)
    - 테이블 4: AI 종합소견
    """

    def __init__(self, template_path: Path | None = None) -> None:
        """초기화.

        Args:
            template_path: 템플릿 파일 경로. None이면 기본 경로 사용.
        """
        self.template_path = template_path or TEMPLATE_PATH

        if not self.template_path.exists():
            raise DocxFillerError(f"템플릿 파일을 찾을 수 없습니다: {self.template_path}")

    def fill_template(self, request: IntegratedReportRequest) -> bytes:
        """템플릿을 데이터로 채웁니다.

        Args:
            request: 통합 보고서 생성 요청 데이터

        Returns:
            채워진 DOCX 파일의 바이트 데이터

        Raises:
            DocxFillerError: 템플릿 채우기 실패 시
        """
        try:
            doc = Document(str(self.template_path))

            # 표지 정보 채우기 (단락에서)
            self._fill_cover_info(doc, request)

            # 테이블 1: 기본 정보
            self._fill_basic_info_table(doc.tables[0], request)

            # 테이블 2: 정서심리 정보
            self._fill_psychological_info_table(doc.tables[1], request)

            # 테이블 3: 의뢰 정보
            self._fill_motivation_table(doc.tables[2], request)

            # 테이블 4: AI 종합소견
            self._fill_ai_summary_table(doc.tables[3], request)

            # 동의 체크박스 처리
            self._fill_consent(doc)

            # 바이트로 변환
            buffer = io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)

            logger.info(
                "DOCX 템플릿 채우기 완료",
                extra={
                    "counsel_request_id": request.counsel_request_id,
                    "child_name": request.child_name,
                },
            )

            return buffer.getvalue()

        except Exception as e:
            logger.error(
                "DOCX 템플릿 채우기 실패",
                extra={"error": str(e), "counsel_request_id": request.counsel_request_id},
            )
            raise DocxFillerError(f"템플릿 채우기 실패: {e}") from e

    def _fill_cover_info(self, doc: Document, request: IntegratedReportRequest) -> None:
        """표지 정보를 채웁니다 (의뢰일자, 센터명, 담당자)."""
        cover = request.cover_info
        date_str = cover.requestDate.to_korean_string()

        for para in doc.paragraphs:
            text = para.text

            # "의뢰일자: 2025년	월	일 센터명:" 패턴 처리
            if "의뢰일자:" in text and "센터명:" in text:
                # 전체 텍스트 재구성
                new_text = f"의뢰일자: {date_str} 센터명: {cover.centerName}"
                para.clear()
                run = para.add_run(new_text)
                run.font.size = Pt(11)

            # "담당자:	(서명)" 패턴 처리
            elif "담당자:" in text:
                new_text = f"담당자: {cover.counselorName} (서명)"
                para.clear()
                run = para.add_run(new_text)
                run.font.size = Pt(11)

    # 우선돌봄 세부 사유 → 한국어 텍스트 매핑
    PRIORITY_REASON_TEXT_MAP: dict[str, str] = {
        "BASIC_LIVELIHOOD": "기초생활보장 수급권자",
        "LOW_INCOME": "차상위계층 가구의 아동",
        "MEDICAL_AID": "의료급여 수급권자",
        "DISABILITY": "장애가구의 아동 또는 장애 아동",
        "MULTICULTURAL": "다문화가족의 아동",
        "SINGLE_PARENT": "한부모가족의 아동",
        "GRANDPARENT": "조손가구의 아동",
        "EDUCATION_SUPPORT": "초･중･고 교육비 지원 대상 아동",
        "MULTI_CHILD": "자녀가 2명 이상인 가구의 아동",
    }

    def _fill_basic_info_table(
        self, table, request: IntegratedReportRequest
    ) -> None:
        """테이블 1: 기본 정보를 채웁니다."""
        child = request.basic_info.childInfo
        care_type = request.basic_info.careType
        priority_reason = request.basic_info.priorityReason

        # Row 0: 이름, 성별, 연령, 학년 값 채우기
        # [0,1]: 이름값, [0,3]: 성별값, [0,5]: 연령값, [0,7]: 학년값
        row = table.rows[0]

        # 셀 인덱스 확인 후 값 설정
        if len(row.cells) > 1:
            row.cells[1].text = child.name
        if len(row.cells) > 3:
            row.cells[3].text = self._gender_to_korean(child.gender)
        if len(row.cells) > 5:
            row.cells[5].text = str(child.age)
        if len(row.cells) > 7:
            row.cells[7].text = child.grade

        # 센터 이용 기준 체크박스 처리 (Row 1-3)
        self._check_care_type(table, care_type, priority_reason)

    def _check_care_type(
        self, table, care_type: str, priority_reason: str | None
    ) -> None:
        """센터 이용 기준 체크박스를 처리합니다.

        Args:
            table: DOCX 테이블 객체
            care_type: 센터 이용 기준 (PRIORITY/GENERAL/SPECIAL)
            priority_reason: 우선돌봄 세부 사유 (careType이 PRIORITY일 때만 사용)
        """
        # careType에 따라 해당 행의 체크박스를 체크
        # PRIORITY -> Row 1, GENERAL -> Row 2, SPECIAL -> Row 3
        row_index = {
            "PRIORITY": 1,
            "GENERAL": 2,
            "SPECIAL": 3,
        }.get(care_type, 1)

        for i in range(1, 4):
            row = table.rows[i]
            cell = row.cells[1]
            text = cell.text

            if i == row_index:
                # 체크 표시로 변경
                cell.text = text.replace("□", "☑")
            else:
                # 빈 체크박스 유지
                cell.text = text.replace("☑", "□")

        # 우선돌봄 아동일 경우 상세 카테고리도 체크
        if care_type == "PRIORITY" and priority_reason:
            self._check_priority_reason(table, priority_reason)

    def _check_priority_reason(self, table, priority_reason: str) -> None:
        """우선돌봄 세부 사유 체크박스를 처리합니다.

        Row 1의 Cell 2~7에 상세 카테고리 체크 항목이 있습니다.
        각 셀에서 해당하는 텍스트를 찾아 □를 ☑로 변경합니다.

        Args:
            table: DOCX 테이블 객체
            priority_reason: 우선돌봄 세부 사유 enum 값
        """
        target_text = self.PRIORITY_REASON_TEXT_MAP.get(priority_reason)
        if not target_text:
            logger.warning(
                "알 수 없는 priorityReason 값",
                extra={"priority_reason": priority_reason},
            )
            return

        # Row 1의 모든 셀을 순회하며 해당 텍스트 찾기
        row = table.rows[1]
        for cell in row.cells:
            cell_text = cell.text
            # 해당 텍스트가 포함된 셀 찾기
            if target_text in cell_text:
                # 해당 라인만 체크 표시
                lines = cell_text.split("\n")
                new_lines = []
                for line in lines:
                    if target_text in line:
                        # 체크박스가 없으면 앞에 추가
                        if "□" not in line and "☑" not in line:
                            new_lines.append(f"☑ {line}")
                        else:
                            new_lines.append(line.replace("□", "☑"))
                    else:
                        new_lines.append(line)
                cell.text = "\n".join(new_lines)
                logger.debug(
                    "우선돌봄 세부 사유 체크 완료",
                    extra={"priority_reason": priority_reason, "target_text": target_text},
                )
                return

        logger.warning(
            "우선돌봄 세부 사유 텍스트를 찾을 수 없음",
            extra={"priority_reason": priority_reason, "target_text": target_text},
        )

    def _fill_psychological_info_table(
        self, table, request: IntegratedReportRequest
    ) -> None:
        """테이블 2: 정서심리 정보를 채웁니다."""
        psych = request.psychological_info

        # Row 0, Col 1: 기존 아동 병력
        if len(table.rows) > 0 and len(table.rows[0].cells) > 1:
            table.rows[0].cells[1].text = psych.medicalHistory or "없음"

        # Row 1, Col 1: 병력 외 특이사항
        if len(table.rows) > 1 and len(table.rows[1].cells) > 1:
            table.rows[1].cells[1].text = psych.specialNotes or "없음"

    def _fill_motivation_table(
        self, table, request: IntegratedReportRequest
    ) -> None:
        """테이블 3: 의뢰 정보를 채웁니다."""
        motivation = request.request_motivation

        # Row 0, Col 1: 의뢰 동기
        if len(table.rows) > 0 and len(table.rows[0].cells) > 1:
            table.rows[0].cells[1].text = motivation.motivation

        # Row 1, Col 1: 보호자 및 의뢰자의 목표
        if len(table.rows) > 1 and len(table.rows[1].cells) > 1:
            table.rows[1].cells[1].text = motivation.goals

    def _fill_ai_summary_table(
        self, table, request: IntegratedReportRequest
    ) -> None:
        """테이블 4: AI 종합소견을 채웁니다."""
        kprc = request.kprc_summary

        # Row 1, Col 0: AI 종합소견 내용
        if len(table.rows) > 1:
            cell = table.rows[1].cells[0]

            # 소견 내용 구성
            content_parts = []

            # 전문가 소견
            if kprc.expertOpinion:
                content_parts.append(kprc.expertOpinion)

            # 요약
            if kprc.summaryLines:
                content_parts.append("\n\n[요약]")
                for line in kprc.summaryLines:
                    content_parts.append(f"• {line}")

            # 핵심 발견사항
            if kprc.keyFindings:
                content_parts.append("\n\n[핵심 발견사항]")
                for finding in kprc.keyFindings:
                    content_parts.append(f"• {finding}")

            # 권장사항
            if kprc.recommendations:
                content_parts.append("\n\n[권장사항]")
                for rec in kprc.recommendations:
                    content_parts.append(f"• {rec}")

            cell.text = "\n".join(content_parts)

            # 셀 스타일 설정
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in para.runs:
                    run.font.size = Pt(10)

    def _fill_consent(self, doc: Document) -> None:
        """동의 체크박스를 처리합니다."""
        for para in doc.paragraphs:
            if "□ 동의" in para.text:
                # 동의에 체크
                para.text = para.text.replace("□ 동의", "☑ 동의")
                break

    def _gender_to_korean(self, gender: str) -> str:
        """성별을 한국어로 변환합니다."""
        return {
            "MALE": "남",
            "FEMALE": "여",
            "M": "남",
            "F": "여",
        }.get(gender.upper(), gender)
