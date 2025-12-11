# yeirin-ai Dockerfile (Local Development)
# LibreOffice headless 포함 - DOCX → PDF 변환용

FROM python:3.12-slim

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    # LibreOffice (DOCX → PDF 변환)
    libreoffice-writer \
    libreoffice-common \
    # 한글 폰트
    fonts-nanum \
    fonts-nanum-coding \
    fonts-nanum-extra \
    # 기타 의존성
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 소스 코드 복사
COPY . .

# 환경 변수
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# 포트 노출
EXPOSE 8001

# 실행
CMD ["uv", "run", "uvicorn", "yeirin_ai.main:app", "--host", "0.0.0.0", "--port", "8001"]
