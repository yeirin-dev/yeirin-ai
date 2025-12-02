#!/bin/bash
# EC2 Ubuntu/Amazon Linux에서 한글 폰트 및 Playwright 의존성 설치 스크립트

set -e

echo "=== 한글 폰트 및 Playwright 의존성 설치 ==="

# OS 감지
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    OS="unknown"
fi

echo "감지된 OS: $OS"

# Ubuntu/Debian 계열
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    echo "Ubuntu/Debian 패키지 설치 중..."
    sudo apt-get update

    # Playwright 의존성
    sudo apt-get install -y \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2

    # 한글 폰트 설치
    sudo apt-get install -y \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        fonts-nanum \
        fonts-nanum-coding \
        fonts-nanum-extra

    # 폰트 캐시 갱신
    sudo fc-cache -fv

# Amazon Linux / RHEL / CentOS 계열
elif [ "$OS" = "amzn" ] || [ "$OS" = "rhel" ] || [ "$OS" = "centos" ]; then
    echo "Amazon Linux/RHEL 패키지 설치 중..."

    # Playwright 의존성
    sudo yum install -y \
        nss \
        nspr \
        atk \
        at-spi2-atk \
        cups-libs \
        libdrm \
        libxkbcommon \
        libXcomposite \
        libXdamage \
        libXfixes \
        libXrandr \
        mesa-libgbm \
        alsa-lib \
        pango \
        cairo

    # 한글 폰트 설치 (Google Noto Fonts)
    sudo yum install -y \
        google-noto-sans-cjk-ttc-fonts \
        google-noto-serif-cjk-ttc-fonts || {
        echo "yum에서 Noto 폰트를 찾을 수 없음, 수동 설치..."

        # 수동 폰트 설치
        mkdir -p ~/.fonts
        cd /tmp

        # Noto Sans Korean 다운로드
        wget -q https://github.com/googlefonts/noto-cjk/releases/download/Sans2.004/03_NotoSansCJK-OTC.zip
        unzip -q 03_NotoSansCJK-OTC.zip -d noto-sans-cjk
        cp noto-sans-cjk/*.ttc ~/.fonts/ 2>/dev/null || true

        # 정리
        rm -rf 03_NotoSansCJK-OTC.zip noto-sans-cjk

        cd -
    }

    # 폰트 캐시 갱신
    fc-cache -fv

else
    echo "지원하지 않는 OS: $OS"
    echo "수동으로 한글 폰트를 설치해주세요."
    exit 1
fi

echo ""
echo "=== 설치 완료 ==="
echo "설치된 한글 폰트 확인:"
fc-list :lang=ko | head -10

echo ""
echo "Playwright 브라우저 설치:"
echo "  uv run playwright install chromium"
