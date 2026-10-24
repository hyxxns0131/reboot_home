# Reboot 실행 안내

README 기획을 기반으로 만든 Flask 브랜드 사이트입니다. 기존 README와 `images/` 원본은 보존했습니다.

## 지금 이 컴퓨터에서 실행

가상환경, 로컬 `.env`, SQLite 데이터베이스를 준비했습니다.

```bash
source .venv/bin/activate
flask --app app:create_app run --debug
```

브라우저에서 http://127.0.0.1:5000 에 접속합니다.

- 구매자 계정: `.env`의 `CUSTOMER_EMAIL` / `CUSTOMER_PASSWORD`
- 관리자 계정: `.env`의 `ADMIN_EMAIL` / `ADMIN_PASSWORD`
- 비밀번호는 무작위 생성되었으며 `.env`에서만 확인할 수 있습니다. Git 제외 대상입니다.
- 로그인하지 않아도 모든 소개 콘텐츠를 볼 수 있습니다.
- 로그아웃 화면의 확인 버튼은 CSRF 보호된 POST 요청으로 세션과 로그인 유지 쿠키를 지웁니다.

## 새 환경에서 설치

Python 3.12 권장. 이 컴퓨터의 Python 3.9에서도 테스트했습니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 충분히 긴 임의 `SECRET_KEY`와 관리자/구매자 이메일·비밀번호를 설정한 다음:

```bash
flask --app app:create_app setup-db
flask --app app:create_app run --debug
```

`setup-db`는 제품 4종·SKU 6종·전용 링크 6개·더미 주문 1,000건을 생성합니다. 기존 계정과 주문을 보존합니다. `.env`의 계정 비밀번호를 나중에 수정해도 기존 DB 계정의 비밀번호는 자동으로 바뀌지 않습니다. 로컬 데이터 전체 삭제가 괜찮을 때만 `FLASK_DEBUG=1 flask --app app:create_app reset-db`를 사용합니다(확인 프롬프트 있음).

## 구현 범위

- 검정/네온 홈, 실제 제공 로고·상품 이미지, 마키, 상품 캐러셀, 반응형 메뉴
- CSS perspective/rotateX/rotateY와 스크롤·포인터 연동 카드 모션. 실제 3D 모델 파일은 사용하지 않습니다.
- 모션 줄이기 설정 지원
- 제품 목록·필터·상세·3가지 맛 이미지 미리보기
- 공개 About / Feed / Where to Buy / Vibe Test / Creators / Contact / Legal
- 회원가입, 구매자·관리자 로그인, 로그아웃 확인/완료 화면
- 구매자 전용 장바구니, 서버 가격 계산, 모의 주문, 본인 주문 내역
- 추천 코드 30일 last-click 귀속, 링크 할인·수수료
- 관리자 기간·상태 필터, 매출 요약 및 UTF-8 BOM CSV 3종
- CSRF, 비밀번호 PBKDF2 해시, 역할 검사, 외부 로그인 리다이렉트 차단, CSV 수식 주입 방어

이미지 파일들은 다각도 도면이어서 CSS로 정면 영역을 표시합니다. Balance 음료의 미확정 당류 문구는 화면에서 CONCEPT 라벨로 가립니다. 최종 홍보용 투명 배경 제품 컷으로 교체하면 더 선명한 색 표현이 가능합니다. 제품 정보 원본은 `products/data/products.json`입니다. 이미지의 젤리 모양과 README의 '스틱 젤리' 설명은 서로 달라, 설명은 README를 유지하고 이미지는 개발 시안으로 표시했습니다.

맛 선택은 시각적 미리보기입니다. README의 SKU는 맛별 구분이 없으므로 주문은 제형·포장 옵션 단위입니다.

## 매출 확인

`/r/NEONNIGHTS` 접속 → 구매자로 로그인 → 제품 담기 → 모의 주문 → 로그아웃 → 관리자로 로그인 → `/admin/`.

- CSV: 상품별 매출 / 링크별 매출 / 주문 품목별 상세
- 기본 기간 최근 90일. 전체 시드는 2026-01-01부터 2026-10-22까지입니다.
- `is_dummy=True`는 시드 주문, `False`는 사용자가 생성한 모의 주문입니다. 실제 결제는 없습니다.
- 클릭 수는 누적, 주문 집계는 선택 기간 기준입니다. 전환율은 선택 기간 주문 수 / 누적 클릭 수입니다.
- `paid` 필터가 기본입니다. `all` 선택 시 취소·환불 표본도 포함하며 회계상 환불 차감 보고서는 아닙니다.

## 검증

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

브라우저 검증(별도 터미널에서 서버 실행):

```bash
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reboot-browser python -m playwright install chromium
python tests/browser_check.py
```

`artifacts/`에 데스크톱·모바일 화면 캡처가 저장됩니다.

## Render

`render.yaml`을 준비했습니다. 외부 배포는 수행하지 않았습니다.

- Build: `pip install -r requirements-render.txt`
- Start: `flask --app app:create_app setup-db && gunicorn -w 2 -b 0.0.0.0:$PORT 'app:create_app()'`
- 운영 환경: `FLASK_DEBUG=0`, `COOKIE_SECURE=1`, `SECRET_KEY`, 계정 환경 변수 4개, `DATABASE_URL`
- PostgreSQL 주소는 `DATABASE_URL`에 설정합니다. `postgres://` 주소는 자동 변환합니다.
- SQLite는 로컬용입니다. Render의 임시 파일시스템에서는 재배포 시 계정·주문이 유실될 수 있으므로 지속 운영에는 PostgreSQL을 사용합니다.

## 아직 연결하지 않은 운영 항목

- 실결제·실배송: 기획대로 모의 주문만 지원합니다.
- Amazon / Weee / Yamibuy: 실제 상품 URL 미제공으로 Coming soon 표시입니다.
- 문의·크리에이터 신청은 DB `core_message`에 저장되며 메일 발송은 설정하지 않았습니다.
- 크리에이터 링크 등록/수정 UI(README Phase 3), 캐릭터, CM송은 미구현입니다. 초기 링크 6개는 작동합니다.
- Legal 문구는 개발용 초안입니다.
