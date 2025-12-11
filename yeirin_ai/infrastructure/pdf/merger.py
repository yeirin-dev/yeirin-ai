"""PDF 병합기.

PyMuPDF(fitz)를 사용하여 여러 PDF 파일을 하나로 병합합니다.
"""

import logging
from pathlib import Path

import fitz  # PyMuPDF


logger = logging.getLogger(__name__)


class PDFMergeError(Exception):
    """PDF 병합 실패 예외."""

    pass


class PDFMerger:
    """PDF 병합기.

    PyMuPDF를 사용하여 여러 PDF 파일을 순서대로 병합합니다.
    상담의뢰지 PDF와 KPRC 검사지 PDF를 병합하는 데 사용됩니다.

    사용법:
        merger = PDFMerger()
        merged_pdf = merger.merge([pdf1_bytes, pdf2_bytes])
    """

    def merge(self, pdfs: list[bytes]) -> bytes:
        """여러 PDF 바이트 데이터를 하나로 병합합니다.

        Args:
            pdfs: 병합할 PDF 바이트 데이터 리스트 (순서대로 병합됨)

        Returns:
            병합된 PDF 바이트 데이터

        Raises:
            PDFMergeError: PDF 병합 실패 시
            ValueError: 빈 리스트가 전달된 경우
        """
        if not pdfs:
            raise ValueError("병합할 PDF가 없습니다")

        if len(pdfs) == 1:
            # 단일 PDF인 경우 그대로 반환
            return pdfs[0]

        try:
            # 새 문서 생성
            merged_doc = fitz.open()

            for idx, pdf_bytes in enumerate(pdfs):
                try:
                    # 각 PDF 열기
                    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

                    # 모든 페이지를 병합 문서에 추가
                    merged_doc.insert_pdf(pdf_doc)

                    logger.debug(
                        f"PDF #{idx + 1} 병합 완료",
                        extra={"pages": len(pdf_doc)},
                    )

                    pdf_doc.close()

                except fitz.FileDataError as e:
                    raise PDFMergeError(
                        f"PDF #{idx + 1} 데이터를 처리할 수 없습니다: {e}"
                    ) from e

            # 바이트로 변환
            merged_bytes = merged_doc.tobytes()
            total_pages = len(merged_doc)
            merged_doc.close()

            logger.info(
                "PDF 병합 완료",
                extra={
                    "input_count": len(pdfs),
                    "total_pages": total_pages,
                    "output_size": len(merged_bytes),
                },
            )

            return merged_bytes

        except PDFMergeError:
            raise
        except Exception as e:
            raise PDFMergeError(f"PDF 병합 중 오류 발생: {e}") from e

    def merge_files(self, file_paths: list[str | Path]) -> bytes:
        """여러 PDF 파일을 하나로 병합합니다.

        Args:
            file_paths: 병합할 PDF 파일 경로 리스트

        Returns:
            병합된 PDF 바이트 데이터

        Raises:
            PDFMergeError: PDF 병합 실패 시
            FileNotFoundError: 파일이 존재하지 않는 경우
        """
        pdf_bytes_list: list[bytes] = []

        for path in file_paths:
            file_path = Path(path)
            if not file_path.exists():
                raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {file_path}")

            if not file_path.suffix.lower() == ".pdf":
                raise PDFMergeError(f"PDF 파일이 아닙니다: {file_path}")

            pdf_bytes_list.append(file_path.read_bytes())

        return self.merge(pdf_bytes_list)

    def merge_with_metadata(
        self,
        pdfs: list[bytes],
        title: str | None = None,
        author: str | None = None,
        subject: str | None = None,
    ) -> bytes:
        """여러 PDF를 병합하고 메타데이터를 설정합니다.

        Args:
            pdfs: 병합할 PDF 바이트 데이터 리스트
            title: PDF 제목
            author: 작성자
            subject: 주제

        Returns:
            병합된 PDF 바이트 데이터 (메타데이터 포함)

        Raises:
            PDFMergeError: PDF 병합 실패 시
        """
        if not pdfs:
            raise ValueError("병합할 PDF가 없습니다")

        try:
            # 새 문서 생성
            merged_doc = fitz.open()

            for idx, pdf_bytes in enumerate(pdfs):
                try:
                    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    merged_doc.insert_pdf(pdf_doc)
                    pdf_doc.close()
                except fitz.FileDataError as e:
                    raise PDFMergeError(
                        f"PDF #{idx + 1} 데이터를 처리할 수 없습니다: {e}"
                    ) from e

            # 메타데이터 설정
            metadata = merged_doc.metadata or {}
            if title:
                metadata["title"] = title
            if author:
                metadata["author"] = author
            if subject:
                metadata["subject"] = subject

            merged_doc.set_metadata(metadata)

            # 바이트로 변환
            merged_bytes = merged_doc.tobytes()
            merged_doc.close()

            logger.info(
                "PDF 병합 완료 (메타데이터 포함)",
                extra={
                    "title": title,
                    "input_count": len(pdfs),
                },
            )

            return merged_bytes

        except PDFMergeError:
            raise
        except Exception as e:
            raise PDFMergeError(f"PDF 병합 중 오류 발생: {e}") from e
