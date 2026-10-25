#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/flask ]]; then
  echo '가상환경이 없습니다. RUNNING.md의 설치 안내를 확인해 주세요.'
  read -r '?Enter를 누르면 닫힙니다.'
  exit 1
fi
printf '\nReboot 사이트: http://127.0.0.1:5050\n이 터미널을 열어 두세요. 종료하려면 Ctrl+C를 누르세요.\n\n'
# DB 테이블 추가 · 더미 데이터 확인 (기존 계정 · 주문은 그대로 유지)
.venv/bin/flask --app app:create_app setup-db || { read -r '?setup-db 실패. Enter를 누르면 닫힙니다.'; exit 1; }
.venv/bin/flask --app app:create_app run --no-debugger --no-reload --host 127.0.0.1 --port 5050
