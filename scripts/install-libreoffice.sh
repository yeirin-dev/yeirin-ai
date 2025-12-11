#!/bin/bash
# EC2 LibreOffice 설치 스크립트 (Ubuntu/Amazon Linux 2)
# 사용법: sudo bash install-libreoffice.sh

set -e

echo "=== LibreOffice 설치 시작 ==="

# OS 감지
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "OS 감지 실패"
    exit 1
fi

case $OS in
    ubuntu|debian)
        echo "Ubuntu/Debian 감지됨"
        apt-get update
        apt-get install -y --no-install-recommends \
            libreoffice-writer \
            libreoffice-common \
            fonts-nanum \
            fonts-nanum-coding \
            fonts-nanum-extra
        ;;
    amzn|amazon)
        echo "Amazon Linux 감지됨"
        yum install -y libreoffice-writer libreoffice-core
        # 한글 폰트 (Amazon Linux)
        yum install -y google-noto-sans-cjk-fonts || true
        ;;
    *)
        echo "지원되지 않는 OS: $OS"
        exit 1
        ;;
esac

# 폰트 캐시 갱신
fc-cache -fv

# 설치 확인
echo ""
echo "=== 설치 확인 ==="
libreoffice --version || soffice --version

echo ""
echo "=== LibreOffice 설치 완료 ==="
echo "경로: $(which libreoffice || which soffice)"
