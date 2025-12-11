"""DOCX 템플릿 채우기.

counsel_request_formatv2.docx 템플릿을 상담의뢰지 데이터로 채웁니다.
"""

import io
import logging
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from yeirin_ai.domain.integrated_report.models import IntegratedReportRequest

logger = logging.getLogger(__name__)

# 나눔고딕 폰트 이름
NANUM_GOTHIC_FONT = "나눔고딕"

# 템플릿 파일 경로 (v2)
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "counsel_request_formatv2.docx"


class DocxFillerError(Exception):
    """DOCX 채우기 에러."""

    pass


class CounselRequestDocxFiller:
    """상담의뢰지 DOCX 템플릿 채우기.

    counsel_request_formatv2.docx 템플릿의 테이블 구조:
    - 테이블 0: 표지 정보 (의뢰일자, 센터명, 담당자)
    - 테이블 1: 섹션 헤더 "1 기본 정보"
    - 테이블 2: 기본 정보 (이름, 성별, 연령, 학년)
    - 테이블 3: 센터 이용 기준 (우선돌봄/일반/돌봄특례 + 상세 사유)
    - 테이블 4: 섹션 헤더 "2 정서·심리 관련 정보"
    - 테이블 5: 정서심리 정보 (병력, 특이사항)
    - 테이블 6: 섹션 헤더 "3 의뢰동기 및 상담목표"
    - 테이블 7: 의뢰 정보 (의뢰동기, 목표)
    - 테이블 8: 섹션 헤더 "4 KPRC 검사결과"
    - 테이블 9: AI 종합소견
    - 테이블 10: 섹션 헤더 "5 보호자 동의 여부"
    - 단락 18: 동의 체크박스
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

            # 테이블 너비 자동 조정 (PDF 변환 시 여백 잘림 방지)
            self._fix_table_widths(doc)

            # 테이블 0: 표지 정보 (의뢰일자, 센터명, 담당자)
            self._fill_cover_table(doc.tables[0], request)

            # 테이블 2: 기본 정보 (이름, 성별, 연령, 학년)
            self._fill_basic_info_table(doc.tables[2], request)

            # 테이블 3: 센터 이용 기준 (체크박스)
            self._fill_care_type_table(doc.tables[3], request)

            # 테이블 5: 정서심리 정보 (병력, 특이사항)
            self._fill_psychological_info_table(doc.tables[5], request)

            # 테이블 7: 의뢰 정보 (의뢰동기, 목표)
            self._fill_motivation_table(doc.tables[7], request)

            # 테이블 9: AI 종합소견
            self._fill_ai_summary_table(doc.tables[9], request)

            # 동의 체크박스 처리 (단락에서)
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

    def _fill_cover_table(self, table, request: IntegratedReportRequest) -> None:
        """테이블 0: 표지 정보를 채웁니다 (의뢰일자, 센터명, 담당자).

        테이블 구조:
        - Row 0: 의뢰일자 | 2025년 월 일
        - Row 1: 센터명 | (빈칸)
        - Row 2: 담당자 | (서명)
        """
        cover = request.cover_info
        date_str = cover.requestDate.to_korean_string()

        # Row 0, Cell 1: 의뢰일자
        if len(table.rows) > 0 and len(table.rows[0].cells) > 1:
            self._set_cell_text_with_font(table.rows[0].cells[1], date_str, font_size=11)

        # Row 1, Cell 1: 센터명
        if len(table.rows) > 1 and len(table.rows[1].cells) > 1:
            self._set_cell_text_with_font(table.rows[1].cells[1], cover.centerName, font_size=11)

        # Row 2, Cell 1: 담당자
        if len(table.rows) > 2 and len(table.rows[2].cells) > 1:
            self._set_cell_text_with_font(
                table.rows[2].cells[1], f"{cover.counselorName} (서명)", font_size=11
            )

    def _fill_basic_info_table(self, table, request: IntegratedReportRequest) -> None:
        """테이블 2: 기본 정보를 채웁니다.

        테이블 구조:
        - Row 0: 이름 | (값) | 성별 | (값) | 연령 | (값)
        - Row 1: 학년 | (값) | ... (merged cells)
        """
        child = request.basic_info.childInfo

        # Row 0: 이름, 성별, 연령
        row0 = table.rows[0]
        if len(row0.cells) > 1:
            self._set_cell_text_with_font(row0.cells[1], child.name, font_size=10)
        if len(row0.cells) > 3:
            self._set_cell_text_with_font(
                row0.cells[3], self._gender_to_korean(child.gender), font_size=10
            )
        if len(row0.cells) > 5:
            self._set_cell_text_with_font(row0.cells[5], str(child.age), font_size=10)

        # Row 1: 학년
        row1 = table.rows[1]
        if len(row1.cells) > 1:
            self._set_cell_text_with_font(row1.cells[1], child.grade, font_size=10)

    # 우선돌봄 세부 사유 → 한국어 텍스트 매핑
    PRIORITY_REASON_TEXT_MAP: dict[str, str] = {
        "BASIC_LIVELIHOOD": "기초생활보장 수급권자",
        "LOW_INCOME": "차상위계층 가구의 아동",
        "MEDICAL_AID": "의료급여 수급권자",
        "DISABILITY": "장애가구의 아동 또는 장애 아동",
        "MULTICULTURAL": "다문화가족의 아동",
        "SINGLE_PARENT": "한부모가족의 아동",
        "GRANDPARENT": "조손가구의 아동",
        "EDUCATION_SUPPORT": "초·중·고 교육비 지원 대상 아동",
        "MULTI_CHILD": "자녀가 2명 이상인 가구의 아동",
    }

    def _fill_care_type_table(self, table, request: IntegratedReportRequest) -> None:
        """테이블 3: 센터 이용 기준 체크박스를 처리합니다.

        테이블 구조:
        - Row 0: 센터이용기준 | □ 우선돌봄아동 | Cell[2]: 상세사유1 | Cell[3]: 상세사유2
        - Row 1: 센터이용기준 | □ 일반 아동 | 설명 | 설명
        - Row 2: 센터이용기준 | □ 돌봄특례아동 | 설명 | 설명
        """
        care_type = request.basic_info.careType
        priority_reason = request.basic_info.priorityReason

        # careType에 따라 해당 행의 체크박스를 체크
        # PRIORITY -> Row 0, GENERAL -> Row 1, SPECIAL -> Row 2
        row_index_map = {
            "PRIORITY": 0,
            "GENERAL": 1,
            "SPECIAL": 2,
        }
        target_row_index = row_index_map.get(care_type, 0)

        for i in range(3):
            if i >= len(table.rows):
                continue
            row = table.rows[i]
            if len(row.cells) > 1:
                cell = row.cells[1]
                text = cell.text
                if i == target_row_index:
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

        Row 0의 Cell 2, Cell 3에 상세 카테고리 체크 항목이 있습니다.
        - Cell 2: 기초생활보장, 차상위계층, 의료급여, 장애가구
        - Cell 3: 다문화가족, 한부모가족, 조손가구, 교육비지원, 자녀2명이상
        """
        target_text = self.PRIORITY_REASON_TEXT_MAP.get(priority_reason)
        if not target_text:
            logger.warning(
                "알 수 없는 priorityReason 값",
                extra={"priority_reason": priority_reason},
            )
            return

        # Row 0의 Cell 2, Cell 3에서 해당 텍스트 찾기
        row = table.rows[0]
        for cell_idx in [2, 3]:
            if cell_idx >= len(row.cells):
                continue
            cell = row.cells[cell_idx]
            cell_text = cell.text

            if target_text in cell_text:
                # 해당 라인만 체크 표시
                lines = cell_text.split("\n")
                new_lines = []
                for line in lines:
                    if target_text in line:
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
        """테이블 5: 정서심리 정보를 채웁니다.

        테이블 구조:
        - Row 0: 기존 아동 병력 | (값)
        - Row 1: 병력 외 특이사항 | (값)
        """
        psych = request.psychological_info

        # Row 0, Col 1: 기존 아동 병력
        if len(table.rows) > 0 and len(table.rows[0].cells) > 1:
            self._set_cell_text_with_font(
                table.rows[0].cells[1], psych.medicalHistory or "없음", font_size=10
            )

        # Row 1, Col 1: 병력 외 특이사항
        if len(table.rows) > 1 and len(table.rows[1].cells) > 1:
            self._set_cell_text_with_font(
                table.rows[1].cells[1], psych.specialNotes or "없음", font_size=10
            )

    def _fill_motivation_table(
        self, table, request: IntegratedReportRequest
    ) -> None:
        """테이블 7: 의뢰 정보를 채웁니다.

        테이블 구조:
        - Row 0: 의뢰 동기 | (값)
        - Row 1: 보호자 및 의뢰자의 목표 | (값)
        """
        motivation = request.request_motivation

        # Row 0, Col 1: 의뢰 동기
        if len(table.rows) > 0 and len(table.rows[0].cells) > 1:
            self._set_cell_text_with_font(
                table.rows[0].cells[1], motivation.motivation, font_size=10
            )

        # Row 1, Col 1: 보호자 및 의뢰자의 목표
        if len(table.rows) > 1 and len(table.rows[1].cells) > 1:
            self._set_cell_text_with_font(
                table.rows[1].cells[1], motivation.goals, font_size=10
            )

    def _fill_ai_summary_table(
        self, table, request: IntegratedReportRequest
    ) -> None:
        """테이블 9: AI 종합소견을 채웁니다.

        테이블 구조:
        - Row 0: 예이린 AI 종합소견 (헤더)
        - Row 1: (내용)
        """
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

            # 나눔고딕 폰트로 셀 채우기
            self._set_cell_text_with_font(cell, "\n".join(content_parts), font_size=10)

            # 셀 스타일 설정 (정렬)
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.LEFT

    def _fill_consent(self, doc: Document) -> None:
        """동의 체크박스를 처리합니다.

        단락 18: □ 동의      □ 미동의
        """
        for para in doc.paragraphs:
            if "□ 동의" in para.text and "□ 미동의" in para.text:
                # 동의에 체크
                para.text = para.text.replace("□ 동의", "☑ 동의", 1)
                break

    def _gender_to_korean(self, gender: str) -> str:
        """성별을 한국어로 변환합니다."""
        return {
            "MALE": "남",
            "FEMALE": "여",
            "M": "남",
            "F": "여",
        }.get(gender.upper(), gender)

    def _set_cell_text_with_font(
        self, cell, text: str, font_size: int = 10, bold: bool = False
    ) -> None:
        """셀에 텍스트를 설정하고 나눔고딕 폰트를 적용합니다."""
        cell.text = ""
        paragraph = cell.paragraphs[0] if cell.paragraphs else cell.add_paragraph()
        paragraph.clear()
        run = paragraph.add_run(text)
        run.font.name = NANUM_GOTHIC_FONT
        run._element.rPr.rFonts.set(qn("w:eastAsia"), NANUM_GOTHIC_FONT)
        run.font.size = Pt(font_size)
        run.font.bold = bold

    def _set_paragraph_text_with_font(
        self, paragraph, text: str, font_size: int = 10, bold: bool = False
    ) -> None:
        """단락에 텍스트를 설정하고 나눔고딕 폰트를 적용합니다."""
        paragraph.clear()
        run = paragraph.add_run(text)
        run.font.name = NANUM_GOTHIC_FONT
        run._element.rPr.rFonts.set(qn("w:eastAsia"), NANUM_GOTHIC_FONT)
        run.font.size = Pt(font_size)
        run.font.bold = bold

    def _fix_table_widths(self, doc: Document) -> None:
        """테이블 너비를 페이지 여백 내로 조정합니다.

        LibreOffice PDF 변환 시 테이블 너비가 페이지를 초과하면
        오른쪽 여백이 잘리는 문제가 발생합니다.
        이 메서드는 tblGrid의 gridCol과 셀 너비를 비례 축소합니다.
        """
        # 페이지 사용 가능 너비 계산 (첫 번째 섹션 기준)
        # DXA/Twips 단위 (1 inch = 1440 dxa/twips, 1 mm ≈ 56.7 dxa)
        # Note: section.page_width는 Twips 객체, .twips로 접근
        section = doc.sections[0]
        page_width_dxa = section.page_width.twips
        left_margin_dxa = section.left_margin.twips
        right_margin_dxa = section.right_margin.twips
        # 안전 마진 2mm (약 113 twips) 추가하여 여유 확보
        safety_margin_dxa = 113
        available_width_dxa = page_width_dxa - left_margin_dxa - right_margin_dxa - safety_margin_dxa

        logger.debug(
            "페이지 설정",
            extra={
                "page_width_mm": section.page_width.mm,
                "available_width_mm": available_width_dxa / 56.7,
            },
        )

        for table_idx, table in enumerate(doc.tables):
            tbl = table._tbl

            # tblGrid에서 그리드 컬럼 너비 확인
            tblGrid = tbl.find(qn("w:tblGrid"))
            if tblGrid is None:
                continue

            gridCols = tblGrid.findall(qn("w:gridCol"))
            if not gridCols:
                continue

            # 그리드 컬럼 너비 합계 계산
            total_grid_width = 0
            grid_widths = []
            for gc in gridCols:
                w = gc.get(qn("w:w"))
                width = int(w) if w else 0
                grid_widths.append(width)
                total_grid_width += width

            # 너비가 페이지를 초과하면 비례 축소
            if total_grid_width > available_width_dxa:
                scale_factor = available_width_dxa / total_grid_width
                logger.debug(
                    f"테이블 {table_idx} 너비 조정",
                    extra={
                        "original_width_mm": total_grid_width / 56.7,
                        "available_width_mm": available_width_dxa / 56.7,
                        "scale_factor": f"{scale_factor:.2f}",
                    },
                )

                # 1. gridCol 너비 축소
                for i, gc in enumerate(gridCols):
                    new_width = int(grid_widths[i] * scale_factor)
                    gc.set(qn("w:w"), str(new_width))

                # 2. 모든 행의 셀 너비 축소
                for row in table.rows:
                    for cell in row.cells:
                        tc = cell._tc
                        tcPr = tc.tcPr
                        if tcPr is not None:
                            tcW = tcPr.find(qn("w:tcW"))
                            if tcW is not None:
                                w_type = tcW.get(qn("w:type"))
                                w_val = tcW.get(qn("w:w"))
                                if w_type == "dxa" and w_val:
                                    new_width = int(int(w_val) * scale_factor)
                                    tcW.set(qn("w:w"), str(new_width))

                # 3. 테이블 가운데 정렬 추가
                tblPr = tbl.tblPr
                if tblPr is None:
                    tblPr = OxmlElement("w:tblPr")
                    tbl.insert(0, tblPr)
                jc = tblPr.find(qn("w:jc"))
                if jc is None:
                    jc = OxmlElement("w:jc")
                    tblPr.append(jc)
                jc.set(qn("w:val"), "center")
