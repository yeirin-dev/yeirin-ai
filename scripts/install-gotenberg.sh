#!/bin/bash
# EC2 Gotenberg Docker 설치 스크립트
# 사용법: bash scripts/install-gotenberg.sh

set -e

echo "=== Gotenberg Docker 컨테이너 설치 ==="

# Docker 설치 확인
if ! command -v docker &> /dev/null; then
    echo "Docker가 설치되어 있지 않습니다. 먼저 Docker를 설치하세요."
    exit 1
fi

# 기존 컨테이너 정리
echo "기존 Gotenberg 컨테이너 정리..."
docker stop gotenberg 2>/dev/null || true
docker rm gotenberg 2>/dev/null || true

# Gotenberg 컨테이너 실행
echo "Gotenberg 컨테이너 시작..."
docker run -d \
    --name gotenberg \
    --restart unless-stopped \
    -p 3001:3000 \
    -e GOTENBERG_API_TIMEOUT=60s \
    -e GOTENBERG_LIBREOFFICE_DISABLE_ROUTES=false \
    gotenberg/gotenberg:8

# 헬스 체크 대기
echo "Gotenberg 시작 대기 중..."
sleep 5

for i in {1..10}; do
    if curl -s http://localhost:3001/health | grep -q "up"; then
        echo ""
        echo "=== Gotenberg 설치 완료 ==="
        echo "URL: http://localhost:3001"
        echo "Health: http://localhost:3001/health"
        echo ""
        echo "yeirin-ai 환경변수 설정:"
        echo "  GOTENBERG_URL=http://localhost:3001"
        exit 0
    fi
    echo "대기 중... ($i/10)"
    sleep 2
done

echo "Gotenberg 시작 실패. 로그 확인:"
docker logs gotenberg
exit 1
