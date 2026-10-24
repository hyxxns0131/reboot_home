# ALDICOM US — Reboot Official Website

> 한국 숙취해소제 기업 **알디콤(ALDICOM)**의 **미국 전용 공식 홈페이지**
> 신규 라인 **Reboot** 4종을 소개하고, **자사몰 구매**와 **인플루언서 전용 링크 매출 관리**까지 하는 브랜드 사이트입니다.
> Flask로 만들고 Render에 배포합니다. 전체 테마와 탭 구성은 [JINRO 글로벌 사이트](https://www.jinro-soju.com/)를 레퍼런스로 합니다.

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [브랜드 · 제품](#2-브랜드--제품)
3. [레퍼런스 분석 → 우리 사이트 구성](#3-레퍼런스-분석--우리-사이트-구성)
4. [사이트맵 · 페이지 구성](#4-사이트맵--페이지-구성)
5. [로그인 · 계정 · 권한](#5-로그인--계정--권한)
6. [구매 기능 (일반 사용자)](#6-구매-기능-일반-사용자)
7. [인플루언서 전용 링크](#7-인플루언서-전용-링크)
8. [관리자 매출 CSV 다운로드](#8-관리자-매출-csv-다운로드)
9. [DB 설계](#9-db-설계)
10. [더미 데이터](#10-더미-데이터)
11. [디자인 가이드](#11-디자인-가이드)
12. [폴더 구조](#12-폴더-구조)
13. [역할 분담 (3명)](#13-역할-분담-3명)
14. [충돌 방지 규칙](#14-충돌-방지-규칙)
15. [제품 데이터 · 이미지 넣는 법](#15-제품-데이터--이미지-넣는-법)
16. [설치 및 실행](#16-설치-및-실행)
17. [환경 변수](#17-환경-변수)
18. [Render 배포](#18-render-배포)
19. [개발 로드맵](#19-개발-로드맵)
20. [카피 · 규제 · 보안 유의사항](#20-카피--규제--보안-유의사항)
21. [회의 메모](#21-회의-메모)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 회사 | **알디콤 (ALDICOM)** — 한국 숙취해소제 기업 |
| 사이트 | 미국 소비자용 공식 브랜드 홈페이지 (영문) |
| 라인 | **Reboot** — 미국 시장 전용 라인 |
| 목적 | 낯선 카테고리를 친숙하게 소개 → 자사몰 구매 · 외부 채널 연결 → 인플루언서 링크 성과 관리 |
| 타깃 | 미국 21세 이상 성인, 특히 MZ세대 (2030) |
| 기술 | Python · Flask · Flask-SQLAlchemy · Flask-Login · Flask-WTF · Jinja2 · Vanilla JS/CSS |
| DB | SQLite (로컬 · 기본) / PostgreSQL (Render, 선택) |
| 배포 | Render (Web Service) |
| 작업 인원 | 3명 |

### 핵심 기능 요약

| 기능 | 비로그인 | 일반 사용자 | 관리자 |
|---|:---:|:---:|:---:|
| 홈페이지 전체 보기 (제품 · Feed · Vibe Test 등) | ✅ | ✅ | ✅ |
| 장바구니 담기 · 주문 (자사몰) | ❌ → 로그인 페이지로 이동 | ✅ | ❌ (관리자는 구매 안 함) |
| 내 주문 내역 | ❌ | ✅ | ❌ |
| 관리자 대시보드 · 매출 CSV 다운로드 | ❌ | ❌ (403) | ✅ |

> **로그인은 선택입니다.** 로그인하지 않아도 모든 소개 페이지를 볼 수 있고, 구매와 관리자 기능만 로그인이 필요합니다.

---

## 2. 브랜드 · 제품

### Reboot 제품 정보

**브랜드 (`brand`)**

| 필드 | 지금 값 | 새 값 |
| --- | --- | --- |
| `base_company` | 알디콤 (실제 데이터 출처) | 알디콤 (ALDICOM) — 한국 숙취해소제 기업. Reboot는 미국 시장 전용 라인 |
| `character` | 리부부 (공식 외형 자료 미제공) | Rebu (이 표기로 통일). 연두색 젤리 몸, 검정 카우보이 모자(초록 별·작은 초록 뿔), 흰 카우보이 부츠 |
| `cm_song` | 니온 앤 리부 (제목만 확인) | 제작 중. 가사·음원 없음 (나중에 추가) |
| `slogan`, `colors`, `category` | 그대로 | 그대로 (Restart Your Day / 검정 & 네온 / 일반식품) |

**제품 4종 공통**

- `ingredients`: `A-HAT + 헛개나무 열매`
    - A-HAT은 알디콤의 특허 조성물입니다. 지구자(헛개나무) 추출물과 유산균 *Lactobacillus fermentum*을 결합한 것입니다.
    - 함량은 받지 못했습니다.
- `flavor_status`: `confirmed`. 최종 패키지에 맛이 인쇄되어 있습니다.
- `consumer_name`: `name`과 같은 값입니다. 미국 홈페이지에 쓰는 제품명이 이 이름입니다.

**젤리 (`jelly_original`, `jelly_balance`)**

| 필드 | Jelly Original | Jelly Balance |
| --- | --- | --- |
| `ko` | Reboot 젤리 | Reboot 제로슈가 젤리 (지금: 저당 젤리) |
| `form` | 개별 포장된 모양 젤리 (카우보이 부츠·카우보이 모자·올가미) | 같음 |
| `flavors` | Lime, Lemon, Cherry (지금: 라임, 체리, 복숭아, 레몬) | Cherry, Lime, Lemon (지금: 레몬·라임) |
| `pack` | 개별 포장된 젤리가 든 한 봉지 (봉지 안 개수 미정) | 같음 |
| `price` | $16 | $18 |
| `direction` | 기본 젤리 | 제로슈가 젤리 (Zero Sugar 표기 조건을 충족했다고 가정) |
| `sugar_reduced` | false | true |

- 젤리 모양은 **부츠·모자·올가미 3가지만** 확정입니다. 일부 사진에 리볼버 모양이 보이지만 확정 모양이 아닙니다.
- 맛과 모양: 체리는 모자(분홍), 레몬은 올가미(노랑), 라임은 부츠(연두)입니다. Balance는 연한 색, Original은 진한 색입니다.

**음료 (`drink_original`, `drink_balance`)**

| 필드 | Drink Original | Drink Balance |
| --- | --- | --- |
| `ko` | Reboot 음료 | Reboot 제로슈가 음료 (지금: 저당 음료) |
| `form` | 비탄산 음료 · 소형 유리병 | 같음 |
| `flavors` | Lemon, Cherry, Lime (지금: 레몬·라임) | Lemon, Lime, Cherry (지금: 레몬·라임) |
| `pack` | 소형 병 낱개 · 3병/박스 (지금: 6병/박스) | 같음 |
| `volume` | 100ml (병 높이 108mm) | 같음 |
| `price` | $7 (낱개). 박스(3병)는 $19 | $8 (낱개). 박스(3병)는 $22 |
| `direction` | 기본 음료 | 제로슈가 음료 (Zero Sugar 표기 조건을 충족했다고 가정) |
| `sugar_reduced` | false | true |

### 주의할 점

3. **Zero Sugar**는 표기 조건을 충족했다고 가정하고 쓰기로 했습니다. Balance 2종에만 해당합니다.
5. 효능(숙취 해소 등)은 성분 정보가 생겨도 계속 쓰지 않습니다.

---

## 3. 레퍼런스 분석 → 우리 사이트 구성

| JINRO 사이트 | 내용 | → Reboot 사이트 |
|---|---|---|
| 상단 탭 | About · Products · Feed · Find JINRO · Vibe test · JINRO AGENT · contact | About · Products · Shop · Feed · Where to Buy · Vibe Test · Creators · Contact |
| 우측 상단 | 언어 · contact | **Login / Logout · 장바구니 · (관리자) Admin** |
| About 하위 | Our Journey / Global Activations | Our Story / (캐릭터 소개 — 미정, 확정 후 추가) |
| 히어로 | 카드 이미지 스택 + 대표 제품 | 대표 제품 카드 스택 (캐릭터 확정 시 추가) |
| 흐르는 문구 | "FILL THE MOMENT" 마키 | **"RESTART YOUR DAY"** 마키 |
| 제품 캐러셀 | Find Your Flavor | **Find Your Reboot** (4종) |
| Find JINRO | 지역별 구매처 | **Where to Buy** (자사몰 + Amazon · Weee · Yamibuy) |
| JINRO Moments | 라이프스타일 이미지 그리드 | **Reboot Moments** |
| Vibe test | 성격 → 맛 추천 퀴즈 | **Vibe Test** (나이트 스타일 → 제품 추천) |
| Feed | 음식 · 문화 콘텐츠 | **Feed** |
| JINRO AGENT | 크리에이터 모집 | **Creators** (협업 신청 + 전용 링크 안내) |

> 레퍼런스는 **구성 · 분위기만** 참고하며, 이미지 · 로고 · 문구는 가져오지 않습니다.

---

## 4. 사이트맵 · 페이지 구성

```
Reboot US (/)
├── /                 ........... Home                         공개
├── /about/story  .............. About (캐릭터 페이지는 확정 후 추가)  공개
├── /products/        ........... 제품 목록                     공개
│   └── /products/<slug> ........ 제품 상세 (+ 장바구니 담기)  공개 (담기는 로그인)
├── /shop/            ........... 자사몰
│   ├── /shop/cart    ........... 장바구니                     🔑 일반 사용자
│   ├── /shop/checkout .......... 주문서 · 주문 완료           🔑 일반 사용자
│   └── /shop/orders  ........... 내 주문 내역                 🔑 일반 사용자
├── /r/<code>         ........... 인플루언서 전용 링크 (추적 후 이동)  공개
├── /feed/ · /feed/<slug> ....... Feed                         공개
├── /where-to-buy/    ........... 구매처                       공개
├── /vibe-test/       ........... Vibe Test                    공개
├── /creators/        ........... 크리에이터 협업              공개
├── /contact/         ........... 문의 폼                      공개
├── /auth/register ............. 회원가입 (일반 사용자)        공개
├── /auth/login · /auth/logout .. 로그인 · 로그아웃            공개
├── /admin/           ........... 관리자 대시보드              🔑 관리자
│   └── /admin/export/<type>.csv  CSV 다운로드                🔑 관리자
└── /legal/           ........... Privacy · Terms · Cookie     공개
```

### Home 섹션 순서

| # | 섹션 | 내용 |
|---|---|---|
| 1 | Hero | 제품 카드 스택 (캐릭터 확정 시 추가), "Restart Your Day", **Shop Now** 버튼 |
| 2 | Marquee | "RESTART YOUR DAY" |
| 3 | Brand Intro | 한국에서 온 after-party ritual 소개 (효능 표현 금지) |
| 4 | Find Your Reboot | 4종 캐러셀 → 상세 페이지 |
| 5 | Where to Buy | 자사몰 + 3채널 배너 |
| 6 | Reboot Moments | 라이프스타일 이미지 그리드 |
| 7 | Vibe Test 배너 | → `/vibe-test/` |
| 8 | Feed 미리보기 | 최신 글 3개 |
| 9 | Footer | SNS · 약관 · 고지문 |

---

## 5. 로그인 · 계정 · 권한

### 원칙

- **회원가입은 누구나 할 수 있고, 가입한 계정은 항상 일반 사용자(`customer`)입니다.** 관리자 계정은 가입으로 만들 수 없습니다. (Supabase 등 외부 인증 서비스 사용 안 함)
- 기본 계정 2개(관리자 · 데모 일반 사용자)는 **환경 변수**에서 읽어 `flask setup-db` 실행 시 DB에 넣습니다. 실제 이메일 · 비밀번호 값은 코드에 쓰지 않습니다. (§17)
- 계정 정보는 `auth_user` 테이블에 저장하며, **비밀번호는 해시(Werkzeug `generate_password_hash`)로만 저장**합니다.

| 계정 | role | 만드는 방법 | 할 수 있는 것 |
|---|---|---|---|
| 관리자 | `admin` | 환경 변수 `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 관리자 대시보드, 매출 CSV 다운로드 |
| 데모 일반 사용자 | `customer` | 환경 변수 `CUSTOMER_EMAIL` / `CUSTOMER_PASSWORD` | 장바구니, 주문, 내 주문 내역 |
| 가입한 일반 사용자 | `customer` | `/auth/register` 회원가입 | 장바구니, 주문, 내 주문 내역 |

### 동작

| 항목 | 내용 |
|---|---|
| 회원가입 | `/auth/register` — 이름 · 이메일 · 비밀번호(8자 이상, 확인 입력) · **21세 이상 체크** 필수, 이메일 중복 불가, CSRF 보호. 가입 즉시 로그인되고 `next` 페이지(없으면 `/`)로 이동 |
| 로그인 | `/auth/login` — 이메일 + 비밀번호, CSRF 보호 (Flask-WTF) |
| 로그인 후 이동 | `next` 파라미터가 있으면 그 페이지로(같은 사이트 경로만 허용), 없으면 관리자는 `/admin/`, 일반 사용자는 직전 페이지 또는 `/` |
| 로그아웃 | `/auth/logout` — **POST 요청**으로만 처리 (헤더의 Logout 버튼이 작은 form) |
| 세션 | Flask-Login, `remember me` 선택 가능 |
| 로그인 필요 페이지 | 비로그인 접근 시 `/auth/login?next=...`로 이동 |
| 권한 없는 접근 | 일반 사용자가 `/admin/` 접근 → 403 페이지 |
| 헤더 표시 | 비로그인: `Sign up` · `Login` / 일반 사용자: `My Orders` · 🛒 · `Logout` / 관리자: `Admin` · `Logout` |

### 권한 데코레이터 (`auth/decorators.py`, 다른 파트에 제공)

```python
from functools import wraps
from flask import abort
from flask_login import current_user, login_required

def role_required(role: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

admin_required = role_required("admin")
customer_required = role_required("customer")
```

---

## 6. 구매 기능 (일반 사용자)

> ⚠️ **실제 결제는 하지 않습니다.** 결제 단계는 "모의 결제(Mock Payment)"이며, 카드 번호 등 결제 정보를 입력받거나 저장하지 않습니다. 주문 버튼을 누르면 주문이 `paid` 상태로 DB에 저장됩니다.

### 흐름

```
제품 상세 → [Add to Cart] ─(비로그인)→ 로그인 → 원래 제품 페이지로 복귀
                │
                ▼
          /shop/cart (수량 변경 · 삭제)
                │
                ▼
        /shop/checkout (배송 정보: 이름 · 주 · 도시 — 데모용)
                │  ※ 인플루언서 링크로 들어왔으면 할인 · 링크 코드 자동 적용
                ▼
        [Place Order (Mock)] → 주문 저장 → 주문 완료 페이지
                │
                ▼
          /shop/orders (내 주문 내역)
```

| 항목 | 내용 |
|---|---|
| 구매 옵션 | 젤리는 한 봉지, 음료는 **개당 / 박스(3개입)** 중 선택 (§2 SKU) |
| 장바구니 저장 | Flask 세션 (`session["cart"] = {sku: qty}`) — DB 저장 안 함 |
| 수량 | 1–10개 |
| 가격 계산 | **서버에서만** 계산 (`shop_product_option.price` 기준). 폼으로 넘어온 가격은 믿지 않음 |
| 주문 저장 | `shop_order` + `shop_order_item` |
| 링크 귀속 | 쿠키 `ref_code`가 있으면 주문에 `referral_link_id` 저장 (§7) |
| 배송비 · 세금 | 데모에선 0으로 고정 |

---

## 7. 인플루언서 전용 링크

인플루언서 마켓(공구 · 협업)마다 **전용 링크**를 발급해, 그 링크로 들어온 주문 매출을 따로 집계합니다.

| 항목 | 내용 |
|---|---|
| 링크 형식 | `https://<도메인>/r/<code>` (예: `/r/NEONNIGHTS`) |
| 동작 | 클릭 수 +1 → 쿠키 `ref_code` 저장(유효 30일) → 홈 또는 지정 제품 페이지로 이동 |
| 귀속 기준 | 주문 시점에 유효한 마지막 `ref_code` (last click) |
| 할인 | 링크별 할인율(`discount_rate`) 주문서에 자동 적용 |
| 수수료 | 링크별 수수료율(`commission_rate`)로 정산 예정액 계산 |
| 관리 | 링크 등록 · 수정은 관리자 페이지에서 (Phase 3) — 초기엔 더미 데이터로 시드 |
| 플랫폼 | 인플루언서는 **Instagram · TikTok 두 플랫폼으로만** 나눠 관리합니다. 링크 코드 = 전용 할인코드 |
| 집계 범위 | **자사몰 주문만** 집계합니다. 유통사(Amazon · Weee · Yamibuy 등) 매출 데이터는 가져오지 않습니다. |

---

## 8. 관리자 매출 CSV 다운로드

관리자로 로그인하면 `/admin/` 대시보드에서 **자사 홈페이지 매출**을 요약해 보고 CSV로 내려받습니다.

### 대시보드 화면

- 기간 필터: 시작일 · 종료일 (기본: 최근 90일), 주문 상태 필터
- 요약 카드: 총 주문 수, 판매 수량, 총 매출(Net), 링크 경유 매출 비중
- 표: 상품별 매출 / **판매 옵션별 매출** / **플랫폼별(Instagram · TikTok) 인플루언서 매출** / 전용 링크별 매출
- CSV 다운로드 버튼: 공통 4개 + 인플루언서 4개 (현재 필터 그대로 적용)

### CSV 종류

| 버튼 | URL | 파일명 예 |
|---|---|---|
| 상품별 매출 | `/admin/export/product-sales.csv?start=2026-01-01&end=2026-10-22` | `reboot_product_sales_20260101_20261022.csv` |
| 전용 링크별 매출 | `/admin/export/link-sales.csv?start=...&end=...` | `reboot_link_sales_20260101_20261022.csv` |
| 주문 상세 (원본) | `/admin/export/orders.csv?start=...&end=...` | `reboot_orders_20260101_20261022.csv` |
| 판매 옵션별 매출 | `/admin/export/option-sales.csv?start=...&end=...` | `reboot_option_sales_20260101_20261022.csv` |
| 인플루언서별 매출 (플랫폼) | `/admin/export/influencer-sales.csv?platform=instagram` (또는 `tiktok`, `all`) | `reboot_influencer_sales_instagram_20260101_20261022.csv` |
| 인플루언서 주문 상세 (플랫폼) | `/admin/export/influencer-orders.csv?platform=tiktok` (또는 `instagram`, `all`) | `reboot_influencer_orders_tiktok_20260101_20261022.csv` |

> `platform`은 `instagram` · `tiktok` · `all`만 허용합니다(그 외 400). 인플루언서 CSV에는 DIRECT(링크 없이 들어온 주문)가 포함되지 않습니다.

#### ① 상품별 매출 (`product-sales.csv`)

| 컬럼 | 설명 |
|---|---|
| `product_slug` | 제품 slug |
| `product_name` | 제품명 |
| `order_count` | 해당 제품이 포함된 주문 수 |
| `units_sold` | 판매 수량 합계 (옵션 단위: 봉지 · 병 · 박스 합산) |
| `box_units_sold` | 그중 박스(3개입) 수량 (젤리는 0) |
| `gross_sales_usd` | 할인 전 매출 |
| `discount_usd` | 할인 합계 |
| `net_sales_usd` | 할인 후 매출 |
| `via_link_sales_usd` | 그중 전용 링크 경유 매출 |

#### ② 전용 링크별 매출 (`link-sales.csv`)

| 컬럼 | 설명 |
|---|---|
| `link_code` | 링크 코드 (`DIRECT` = 링크 없이 들어온 주문) |
| `influencer_name` | 인플루언서 이름 (가상) |
| `platform` | TikTok / Instagram |
| `clicks` | 링크 클릭 수 |
| `order_count` | 주문 수 |
| `conversion_rate` | 주문 수 ÷ 클릭 수 |
| `units_sold` | 판매 수량 |
| `net_sales_usd` | 할인 후 매출 |
| `commission_usd` | 정산 예정 수수료 |
| `top_product` | 가장 많이 팔린 제품 |

#### ④ 판매 옵션별 매출 (`option-sales.csv`)

판매 중인 **모든 옵션(SKU)** 이 한 줄씩 나옵니다. 기간 내 판매가 0건이어도 행이 나옵니다.
젤리는 맛별이 아니라 **라인별 패키지(3가지 맛 구성) 1개 옵션**만 있고, 음료는 맛별 낱병 3개 + 믹스 박스(3병) 1개 옵션입니다. → 총 10개 옵션

| 컬럼 | 설명 |
|---|---|
| `product_slug` · `product_name` · `product_line` | 제품 · 라인 (`Jelly` / `Drink`) |
| `option_sku` · `option_label` | 판매 옵션 |
| `pack_size` | 옵션 1개에 든 개수 (박스 = 3) |
| `list_price_usd` | 옵션 정가 |
| `order_count` | 이 옵션이 포함된 주문 수 |
| `quantity_sold` | 옵션 판매 수량 |
| `pieces_sold` | 병 · 패키지 기준 개수 (`quantity_sold × pack_size`) |
| `gross_sales_usd` · `discount_usd` · `net_sales_usd` | 할인 전 · 할인 · 할인 후 매출 |
| `direct_sales_usd` · `instagram_sales_usd` · `tiktok_sales_usd` | 유입 경로별 순매출 (세 값의 합 = `net_sales_usd`) |

#### ⑤ 인플루언서별 매출 (`influencer-sales.csv?platform=`)

`platform, influencer_name, discount_code, link_path, discount_rate, commission_rate, clicks, order_count, conversion_rate, units_sold, gross_sales_usd, discount_usd, net_sales_usd, commission_usd, top_product`
(인플루언서 1명 = 1행. `discount_code`는 링크 코드와 같고 `link_path`는 `/r/<code>`)

#### ⑥ 인플루언서 주문 상세 (`influencer-orders.csv?platform=`)

`order_id, ordered_at, status, platform, influencer_name, discount_code, link_path, discount_rate, product_slug, product_name, option_sku, option_label, quantity, unit_price_usd, gross_usd, discount_usd, line_total_usd, commission_rate, commission_usd, ship_state, is_dummy`
(전용 링크로 들어온 주문의 품목 1줄 = 1행, `commission_usd = line_total_usd × commission_rate`)

#### ③ 주문 상세 (`orders.csv`)

`order_id, ordered_at, status, product_slug, product_name, option_sku, option_label, quantity, unit_price_usd, discount_usd, line_total_usd, link_code, influencer_name, ship_state, is_dummy`
(주문 품목 1줄 = CSV 1행)

### 구현 규칙

- 파이썬 기본 `csv` 모듈 + `io.StringIO`로 만들고 `Response(mimetype="text/csv")`로 반환
- 인코딩은 **`utf-8-sig`** (엑셀에서 열 때 깨지지 않게)
- 금액은 소수 2자리, 날짜는 ISO 형식 (`2026-10-22T21:15:00`)
- 모든 `/admin/*` 라우트에 `@admin_required` 필수
- CSV 셀이 `=`, `+`, `-`, `@`로 시작하면 앞에 `'`를 붙여 **CSV 수식 주입**을 막습니다

---

## 9. DB 설계

테이블 이름은 **파트 이름을 접두사**로 붙입니다.

```
auth_user ───────────────┐
                         │ 1:N
shop_referral_link ──┐   ▼
        1:N          └─▶ shop_order ──1:N──▶ shop_order_item ◀──N:1── shop_product_option ◀──N:1── shop_product
```

| 테이블 | 담당 파트 | 주요 컬럼 |
|---|---|---|
| `auth_user` | auth | `id`, `email`(unique), `password_hash`, `role`(`admin`/`customer`), `name`, `created_at` |
| `shop_product` | shop | `id`, `slug`(unique), `name`, `is_active` — `products.json`에서 동기화 |
| `shop_product_option` | shop | `id`, `product_id`(FK), `sku`(unique), `label`(`1 Pouch`/`1 Bottle`/`Box of 3`), `unit_count`, `price`(Numeric 10,2), `is_active` — `products.json`의 `options`에서 동기화 |
| `shop_referral_link` | shop | `id`, `code`(unique), `influencer_name`, `platform`, `discount_rate`, `commission_rate`, `clicks`, `is_active`, `created_at` |
| `shop_order` | shop | `id`, `user_id`(nullable, FK), `referral_link_id`(nullable, FK), `status`(`paid`/`refunded`/`cancelled`), `subtotal`, `discount`, `total`, `ship_name`, `ship_state`, `ship_city`, `is_dummy`, `ordered_at` |
| `shop_order_item` | shop | `id`, `order_id`(FK), `product_id`(FK), `option_id`(FK), `quantity`, `unit_price`, `line_discount`, `line_total` |

> - 금액은 `Numeric(10, 2)`로 저장합니다. (float 금지)
> - 더미 주문은 `is_dummy=True`, `user_id=NULL`이며 실제 일반 사용자 주문과 구분됩니다.
> - 관리자 CSV에는 더미 · 실제 주문이 모두 포함되고 `is_dummy` 컬럼으로 구분합니다.

---

## 10. 더미 데이터

`flask setup-db` 실행 시 자동으로 들어갑니다. **같은 시드값(`random.seed(42)`)을 써서 누가 실행해도 같은 데이터**가 만들어집니다.

### 최소 수량 기준 (✅ 각각 100건 이상)

| 대상 | 기준 | 생성 계획 |
|---|---|---|
| 전체 주문 | — | **1,000건** (`2026-01-01 ~ 2026-10-22`) |
| **상품별** | 4종 **각각 주문 100건 이상** | 주문당 1–3개 품목, 각 제품 최소 150건 보장 (음료는 개당 · 박스 옵션 섞어서) |
| **판매 옵션별** | 옵션 10개 **각각 주문 100건 이상** | 주문의 첫 제품이 판매 옵션을 차례로 돌아가며 선택 → 옵션마다 100건 이상 보장 |
| **전용 링크별** | 링크 **각각 주문 100건 이상** | 인플루언서 링크 6개 × 각 120건 = 720건 |
| **플랫폼별** | Instagram · TikTok **각각 100건 이상** | Instagram 3명 × 120 = 360건 / TikTok 3명 × 120 = 360건 |
| 링크 없는 주문 (DIRECT) | — | 280건 |
| 링크 클릭 수 | 주문 수보다 큼 | 링크별 주문 수 × 8–20배 |

### 더미 인플루언서 링크 6개 (모두 가상 인물)

| code | influencer_name | platform | 할인 | 수수료 |
|---|---|---|---|---|
| `NEONNIGHTS` | Neon Nights (가상) | TikTok | 10% | 15% |
| `KPARTYLA` | K-Party LA (가상) | Instagram | 10% | 12% |
| `MORNINGRESET` | Morning Reset (가상) | Instagram | 15% | 15% |
| `SEOULSIPNYC` | Seoul Sip NYC (가상) | TikTok | 10% | 10% |
| `BRUNCHCLUB` | Brunch Club (가상) | Instagram | 5% | 10% |
| `RESTARTCREW` | Restart Crew (가상) | TikTok | 20% | 20% |

### 생성 규칙

- 주문 시각: 금 · 토 밤, 핼러윈 · 추수감사절 전후 · 연말에 가중치 (미국 음주 시즌 반영)
- 배송 주(state): CA · NY · TX · WA · NJ · IL 등 MZ세대 인구가 많은 대도시권 주에 가중치
- 상태: `paid` 95% / `refunded` 3% / `cancelled` 2%
- 이름 · 주소는 가상 데이터만 사용 (실존 인물 · 주소 금지)
- 생성 후 **검증 assert**: 각 제품 · 각 판매 옵션 · 각 링크 · Instagram/TikTok 플랫폼 주문 수 ≥ 100을 확인하고, 실패하면 시드를 중단합니다.
- 이미 만든 로컬 DB에 새 규칙의 더미 데이터를 다시 넣으려면 `flask --app app:create_app reset-db`를 실행합니다. (`setup-db`는 기존 더미 주문이 있으면 건너뛰고, 링크 플랫폼만 Instagram/TikTok으로 맞춥니다.)

### 더미 CSV 샘플 파일 (`sample_exports/`)

`2026-01-01 ~ 2026-10-25`, 주문 상태 `paid` 기준으로 관리자 CSV 8종을 뽑아 둔 파일입니다. (상품별 · 옵션별 · 링크별 · 주문 상세 + Instagram/TikTok 인플루언서별 · 인플루언서 주문 상세) 시드를 바꾸면 다시 뽑습니다.

```python
# shop/seed.py (요약)
def seed_dummy_orders(n_orders=1000, seed=42):
    rng = random.Random(seed)
    ...
    assert all(c >= 100 for c in product_order_counts.values())
    assert all(c >= 100 for c in link_order_counts.values())
```

### CLI 명령 (`core/cli.py`)

| 명령 | 내용 |
|---|---|
| `flask setup-db` | 테이블 생성 → 계정 2개 → 제품 4종 → 링크 6개 → 더미 주문 1,000건. **이미 있으면 건너뜀(중복 생성 안 함)** |
| `flask reset-db` | 전체 삭제 후 다시 생성 (로컬 전용, `FLASK_DEBUG=1`일 때만 동작) |

`core/cli.py`는 각 파트의 시드 함수를 순서대로 **호출만** 합니다. (`auth.seed.seed_accounts()`, `shop.seed.seed_products()`, `shop.seed.seed_links()`, `shop.seed.seed_dummy_orders()`)

---

## 11. 디자인 가이드

JINRO 사이트의 **어두운 배경 + 굵은 대문자 타이포 + 큰 제품 이미지 + 마키 + 캐러셀** 구조를 따르고, 색은 Reboot의 **검정 & 네온**으로 바꿉니다.

### 색상 토큰 (`core/static/core/css/tokens.css`)

```css
:root {
  --color-bg:        #0A0A0A;
  --color-surface:   #161616;
  --color-text:      #FFFFFF;
  --color-muted:     #9A9A9A;
  --color-neon:      #39FF14;   /* 메인 네온 (임시값) */
  --color-neon-2:    #00E5FF;   /* 보조 네온 (임시값) */
  --color-line:      #2A2A2A;
  --color-danger:    #FF4D6D;

  --font-display: "Anton", "Bebas Neue", sans-serif;
  --font-body:    "Inter", system-ui, sans-serif;

  --radius: 16px;
  --container: 1280px;
}
```

### 공통 UI 컴포넌트 (core 제공)

| 컴포넌트 | 파일 |
|---|---|
| 헤더 · 상단 탭 · 로그인 상태 영역 · 모바일 메뉴 | `core/templates/core/_header.html` |
| 푸터 | `core/templates/core/_footer.html` |
| 플래시 메시지 (로그인 성공 · 오류 등) | `core/templates/core/_flash.html` |
| 마키 | `core/templates/core/_marquee.html` |
| 제품 카드 | `core/templates/core/_product_card.html` |
| 버튼 · 폼 · 표 | `.btn`, `.btn--neon`, `.form-field`, `.table` (`components.css`) |
| 이미지 자리표시자 | `core/static/core/img/placeholder.svg` |

> 관리자 화면(`/admin`)도 같은 토큰을 쓰되, 데이터 표가 잘 보이도록 마키 · 큰 히어로 없이 단순한 레이아웃(`admin/base_admin.html`)을 씁니다.

---

## 12. 폴더 구조

> 3명이 동시에 작업하므로 **파트별로 Blueprint 폴더를 완전히 분리**합니다.

```
aldicom-us-website/
├── app.py                    # create_app() · 확장 초기화 · Blueprint 등록 (🔒 공통)
├── config.py                 # 설정값 (🔒 공통)
├── requirements.txt          # (🔒 공통)
├── .env.example              # (🔒 공통, 값 없음)
├── .python-version           # Render용 Python 버전
├── render.yaml               # (🔒 공통)
├── .gitignore                # .env, instance/, *.db 포함
├── README.md
│
├── core/                     # 🔒 공통 ............................ A
│   ├── __init__.py
│   ├── extensions.py         #    db, login_manager, csrf 객체 (한 곳에서만 생성)
│   ├── cli.py                #    flask setup-db / reset-db
│   ├── nav.py                #    상단 탭 목록 NAV_ITEMS
│   ├── templates/core/       #    base.html, _header, _footer, _flash, _marquee, _product_card, errors/403·404·500
│   └── static/core/          #    css/ · js/ · fonts/ · img/
│
├── main/                     # 🏠 Home (/) ........................ A
├── about/                    # 📖 About (/about) .................. A
├── legal/                    # 📄 약관 (/legal) ................... A
├── auth/                     # 🔐 로그인 · 로그아웃 (/auth) ......... A
│   ├── models.py             #    auth_user
│   ├── forms.py              #    LoginForm
│   ├── decorators.py         #    admin_required, customer_required (다른 파트 제공)
│   └── seed.py               #    seed_accounts() — 환경 변수로 계정 2개 생성
│
├── products/                 # 🧃 제품 소개 (/products) ........... B
│   └── data/products.json    #    ⭐ 제품 4종 데이터 (단일 원본)
├── shop/                     # 🛒 자사몰 · 주문 · 전용 링크 (/shop, /r) . B
│   ├── models.py             #    shop_product, shop_product_option, shop_referral_link, shop_order, shop_order_item
│   ├── cart.py               #    세션 장바구니 로직
│   ├── services.py           #    주문 생성 · 가격 계산 · 링크 귀속
│   ├── referral.py           #    /r/<code> Blueprint (url_prefix 없음)
│   └── seed.py               #    seed_products / seed_links / seed_dummy_orders
├── where_to_buy/             # 🗺️ 구매처 (/where-to-buy) .......... B
│
├── admin/                    # 📊 관리자 대시보드 · CSV (/admin) ... C
│   ├── services.py           #    상품별 · 링크별 · 주문 상세 집계 쿼리 (읽기 전용)
│   ├── export.py             #    CSV 생성 (utf-8-sig, 수식 주입 방지)
│   └── templates/admin/      #    base_admin.html, dashboard.html
├── vibe_test/                # 🎯 Vibe Test (/vibe-test) .......... C
├── feed/                     # 📰 Feed (/feed) .................... C
├── creators/                 # 🤝 Creators (/creators) ............ C
├── contact/                  # ✉️ Contact (/contact) .............. C
│
├── tests/                    # 파트별 하위 폴더 (tests/auth/, tests/shop/, tests/admin/ ...)
└── instance/                 # 로컬 SQLite (Git 제외)
```

### 파트 폴더 내부 구성 (모든 파트 동일)

```
shop/
├── __init__.py          # Blueprint 정의 (url_prefix="/shop")
├── routes.py            # URL · 화면 연결
├── services.py          # 로직
├── models.py            # 이 파트 테이블 (필요한 파트만)
├── forms.py             # 폼 (필요한 파트만)
├── seed.py              # 더미 데이터 (필요한 파트만)
├── data/
├── templates/shop/      # ← 파트 이름 폴더로 감싸기
├── static/shop/         # ← 파트 이름 폴더로 감싸기
└── README.md            # 파트 설명 · 다른 파트에 제공하는 함수
```

### `app.py` (Phase 0에 A가 완성 — 이후 수정 없음)

```python
from flask import Flask
from config import Config
from core.extensions import db, login_manager, csrf

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)

    # 모델 import (테이블 등록용)
    import auth.models, shop.models  # noqa: F401

    from core import bp as core_bp
    from main import bp as main_bp
    from about import bp as about_bp
    from legal import bp as legal_bp
    from auth import bp as auth_bp
    from products import bp as products_bp
    from shop import bp as shop_bp
    from shop.referral import bp as referral_bp
    from where_to_buy import bp as where_to_buy_bp
    from admin import bp as admin_bp
    from vibe_test import bp as vibe_test_bp
    from feed import bp as feed_bp
    from creators import bp as creators_bp
    from contact import bp as contact_bp

    for bp in (core_bp, main_bp, about_bp, legal_bp, auth_bp, products_bp,
               shop_bp, referral_bp, where_to_buy_bp, admin_bp,
               vibe_test_bp, feed_bp, creators_bp, contact_bp):
        app.register_blueprint(bp)

    from core.cli import register_cli
    register_cli(app)

    from core.nav import NAV_ITEMS
    app.jinja_env.globals["NAV_ITEMS"] = NAV_ITEMS
    return app
```

> **첫 커밋에서 모든 Blueprint를 빈 페이지로 미리 만들어 등록**해 두면, 이후 누구도 `app.py`를 고칠 일이 없습니다.

---

## 13. 역할 분담 (3명)

| 담당 | 파트 | 폴더 | 주요 작업 |
|---|---|---|---|
| **A** (이름: ___) | 공통 · 로그인 · 소개 | `core/`, `auth/`, `main/`, `about/`, `legal/` | 초기 세팅, `extensions.py` · `cli.py`, base 레이아웃 · 헤더(로그인 상태), 로그인 · 로그아웃 · 권한 데코레이터 · 계정 시드, Home · About · 약관 |
| **B** (이름: ___) | 제품 · 구매 · 전용 링크 | `products/`, `shop/`, `where_to_buy/` | 제품 데이터 · 목록 · 상세, 장바구니 · 주문 · 내 주문, `/r/<code>` 링크 추적, 주문 모델 · **더미 데이터 시드** |
| **C** (이름: ___) | 관리자 · 콘텐츠 | `admin/`, `vibe_test/`, `feed/`, `creators/`, `contact/` | 관리자 대시보드 · **CSV 3종 다운로드**, Vibe Test, Feed, Creators, Contact |

- 브랜치 이름: `feature/이니셜-기능명` (예: `feature/B-checkout`, `feature/C-csv-export`)

### 파트 간 의존 관계 · 작업 순서

```
A: core + auth (Phase 0) ──────────────┐
                                        ▼
B: shop/models.py 먼저 확정 → 더미 시드 ──▶ C: admin 집계 · CSV
        │
        └─ products.services ──▶ main(A) 캐러셀, vibe_test(C) 결과
```

1. **A**가 `core/extensions.py`, `auth`, 빈 Blueprint 전체를 먼저 `dev`에 병합합니다.
2. **B**가 `shop/models.py`(§9 컬럼 그대로)와 `shop/seed.py`를 **가장 먼저** PR합니다.
3. **C**는 그 전까지 §8 CSV 컬럼 기준으로 화면 · `export.py`를 만들고, 모델 병합 후 집계 쿼리를 붙입니다.

### 다른 파트에 제공하는 함수

| 제공 파트 | 함수 | 사용하는 곳 |
|---|---|---|
| `auth.decorators` | `admin_required`, `customer_required` | shop(B), admin(C) |
| `products.services` | `get_all_products()`, `get_product(slug)` | main(A), shop(B), vibe_test(C) |
| `shop.models` | `Order`, `OrderItem`, `Product`, `ProductOption`, `ReferralLink` (**읽기 전용 import**) | admin(C) |

---

## 14. 충돌 방지 규칙

| 규칙 | 내용 |
|---|---|
| **내 폴더만 수정** | 자기 파트 폴더 밖은 수정하지 않습니다. |
| **공통 영역은 A가 관리** | `app.py`, `config.py`, `requirements.txt`, `.env.example`, `render.yaml`, `core/` — 수정이 필요하면 A와 협의 후 PR에 `[공통]` 표시 |
| **확장 객체는 한 곳에서만** | `db`, `login_manager`, `csrf`는 `core/extensions.py`에서만 만들고 `from core.extensions import db`로 가져옵니다. 파트에서 `SQLAlchemy()`를 새로 만들지 않습니다. |
| **DB 테이블 이름** | 파트 접두사 필수: `auth_user`, `shop_order` … |
| **모델 수정** | 테이블은 만든 파트만 수정합니다. C는 `shop.models`를 읽기만 합니다. 컬럼 추가가 필요하면 B에게 요청합니다. |
| **URL 접두사 고정** | `/`, `/about`, `/legal`, `/auth`, `/products`, `/shop`, `/r`, `/where-to-buy`, `/admin`, `/vibe-test`, `/feed`, `/creators`, `/contact` |
| **템플릿 경로** | `render_template("파트명/파일.html")` |
| **CSS 클래스 접두사** | `.shop-cart`, `.admin-table`, `.vibe-question` 등. 공통 클래스는 core에만 |
| **CSS · JS 로드** | 자기 템플릿의 `{% block extra_css %}` · `{% block extra_js %}`에서만 |
| **색 · 폰트** | 토큰(`var(--color-neon)`)만 사용 |
| **상단 탭** | `core/nav.py`만 수정 (A) |
| **제품 정보** | `products/data/products.json` 한 곳 (B). `shop_product` · `shop_product_option`은 시드 때 이 파일에서 동기화 |
| **브랜치** | `main` · `dev` 직접 push 금지. `dev`로 PR → 확인 후 `main` 병합 (Render는 `main`만 배포) |
| **한 PR = 한 파트** | 두 파트를 맡아도 PR은 파트마다 따로 |
| **패키지 추가** | 버전 고정 한 줄 추가 + PR에 이유. `pip freeze` 덮어쓰기 금지 |
| **DB 파일** | `instance/*.db`는 Git에 올리지 않습니다. 각자 `flask setup-db`로 만듭니다. |

---

## 15. 제품 데이터 · 이미지 넣는 법

### `products/data/products.json`

```json
[
  {
    "slug": "jelly-original",
    "name": "Reboot Jelly Original",
    "line": "Jelly",
    "format": "Individually wrapped shaped jelly (cowboy boot, cowboy hat, lasso)",
    "pack": "Individually wrapped pouch",
    "ingredients": ["A-HAT", "Hovenia dulcis (Oriental raisin tree) fruit"],
    "flavors": ["Lime", "Cherry", "Lemon"],
    "options": [
      { "sku": "jelly-original-pouch", "label": "1 Pouch", "unit_count": 1, "price_usd": 16.00 }
    ],
    "price_is_sample": true,
    "is_balance": false,
    "tagline": "TBD",
    "images": { "main": "jelly-original-main.webp", "gallery": [] },
    "buy_links": { "amazon": "", "weee": "", "yamibuy": "" },
    "order": 1
  },
  {
    "slug": "jelly-balance",
    "name": "Reboot Jelly Balance",
    "line": "Jelly",
    "format": "Individually wrapped shaped jelly (cowboy boot, cowboy hat, lasso)",
    "pack": "Individually wrapped pouch",
    "ingredients": ["A-HAT", "Hovenia dulcis (Oriental raisin tree) fruit"],
    "flavors": ["Lemon", "Cherry", "Lime"],
    "options": [
      { "sku": "jelly-balance-pouch", "label": "1 Pouch", "unit_count": 1, "price_usd": 18.00 }
    ],
    "price_is_sample": true,
    "is_balance": true,
    "tagline": "TBD",
    "images": { "main": "jelly-balance-main.webp", "gallery": [] },
    "buy_links": { "amazon": "", "weee": "", "yamibuy": "" },
    "order": 2
  },
  {
    "slug": "drink-original",
    "name": "Reboot Drink Original",
    "line": "Drink",
    "format": "Non-carbonated drink",
    "volume": "100ml",
    "pack": "Small bottle (single) or box of 3",
    "ingredients": ["A-HAT", "Hovenia dulcis (Oriental raisin tree) fruit"],
    "flavors": ["Lemon", "Cherry", "Lime"],
    "options": [
      { "sku": "drink-original-single", "label": "1 Bottle", "unit_count": 1, "price_usd": 7.00 },
      { "sku": "drink-original-box3", "label": "Box of 3", "unit_count": 3, "price_usd": 19.00 }
    ],
    "price_is_sample": true,
    "is_balance": false,
    "tagline": "TBD",
    "images": { "main": "drink-original-main.webp", "gallery": [] },
    "buy_links": { "amazon": "", "weee": "", "yamibuy": "" },
    "order": 3
  },
  {
    "slug": "drink-balance",
    "name": "Reboot Drink Balance",
    "line": "Drink",
    "format": "Non-carbonated drink",
    "volume": "100ml",
    "pack": "Small bottle (single) or box of 3",
    "ingredients": ["A-HAT", "Hovenia dulcis (Oriental raisin tree) fruit"],
    "flavors": ["Lemon", "Lime", "Cherry"],
    "options": [
      { "sku": "drink-balance-single", "label": "1 Bottle", "unit_count": 1, "price_usd": 8.00 },
      { "sku": "drink-balance-box3", "label": "Box of 3", "unit_count": 3, "price_usd": 22.00 }
    ],
    "price_is_sample": true,
    "is_balance": true,
    "tagline": "TBD",
    "images": { "main": "drink-balance-main.webp", "gallery": [] },
    "buy_links": { "amazon": "", "weee": "", "yamibuy": "" },
    "order": 4
  }
]
```

> 빈 외부 구매 링크(`""`)는 "Coming Soon"으로 표시합니다.

### 이미지 넣기 (나중에 교체)

파일이 없으면 `core/static/core/img/placeholder.svg`가 자동 표시되므로, **정해진 파일명으로 넣기만 하면** 교체됩니다.
권장: `.webp`, 제품 컷 1200×1200 투명 배경, 배너 1920×1080, 한 장 500KB 이하.

| 위치 | 경로 | 담당 |
|---|---|---|
| 로고 · 파비콘 (캐릭터 확정 후 캐릭터 이미지도) | `core/static/core/img/` | A |
| Home 히어로 · Moments | `main/static/main/images/` | A |
| 제품 컷 (`<slug>-main.webp`) | `products/static/products/images/` | B |
| 구매처 로고 | `where_to_buy/static/where_to_buy/images/` | B |
| Vibe Test 결과 | `vibe_test/static/vibe_test/images/` | C |
| Feed 썸네일 | `feed/static/feed/images/` | C |

---

## 16. 설치 및 실행

명령은 Windows `cmd` 기준입니다. (macOS · Linux는 `source venv/bin/activate`, `cp`)

```cmd
git clone <repository-url>
cd aldicom-us-website
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env`에 `SECRET_KEY`와 계정 4개 값(`ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CUSTOMER_EMAIL`, `CUSTOMER_PASSWORD`)을 채운 뒤:

```cmd
flask --app app:create_app setup-db
flask --app app:create_app run --debug
```

- 접속: `http://127.0.0.1:5000`
- 관리자: `.env`의 `ADMIN_EMAIL`로 로그인 → `/admin/`
- 일반 사용자: `.env`의 `CUSTOMER_EMAIL`로 로그인 → 제품 담기 · 주문
- 링크 테스트: `http://127.0.0.1:5000/r/NEONNIGHTS` 접속 후 주문 → 관리자 CSV에서 확인

### `requirements.txt` (초기)

```txt
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.2.1
gunicorn==22.0.0
python-dotenv==1.0.1
psycopg2-binary==2.9.9
```

> `psycopg2-binary`는 Render PostgreSQL을 쓸 때만 필요합니다. SQLite만 쓰면 빼도 됩니다.

---

## 17. 환경 변수

`.env.example`

```env
# Flask
SECRET_KEY=change-me
FLASK_DEBUG=1

# DB (비우면 instance/reboot.db SQLite 사용)
DATABASE_URL=

# 계정 2개 (setup-db 때 DB에 해시로 저장)
ADMIN_EMAIL=
ADMIN_PASSWORD=
CUSTOMER_EMAIL=
CUSTOMER_PASSWORD=

# 사이트
SITE_URL=http://127.0.0.1:5000
REF_COOKIE_DAYS=30

# 더미 데이터
SEED_DUMMY_DATA=1

# Contact / Creators 폼 알림 메일 (선택)
MAIL_SERVER=
MAIL_PORT=587
MAIL_USERNAME=
MAIL_PASSWORD=
CONTACT_RECEIVER=
```

> ⚠️ `.env`는 절대 Git에 커밋하지 않습니다. 계정 비밀번호를 README · 코드 · PR · 슬랙에 적지 않고, 팀원끼리는 별도로 전달합니다.
> 계정 4개 값이 비어 있으면 `setup-db`가 오류를 내고 멈춥니다.

---

## 18. Render 배포

### 설정값

| 항목 | 값 |
|---|---|
| Service Type | Web Service |
| Runtime | Python 3 |
| Branch | `main` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `flask --app app:create_app setup-db && gunicorn -w 2 -b 0.0.0.0:$PORT "app:create_app()"` |
| Python 버전 | 루트 `.python-version` (예: `3.12`) 또는 `PYTHON_VERSION` 환경 변수 |
| Environment | §17 변수 등록 (`FLASK_DEBUG=0`, 계정 4개, `SECRET_KEY`) |

> `setup-db`는 이미 데이터가 있으면 건너뛰므로 매번 실행해도 안전합니다.

### DB 선택 — 꼭 읽어 주세요

| 방식 | 장점 | 주의 |
|---|---|---|
| **SQLite (기본)** | 설정 없음 | Render 파일시스템은 재배포 · 재시작 때 초기화됩니다. 시작할 때마다 `setup-db`가 계정 2개 + 더미 1,000건을 **다시 만들어** 시연에는 문제없지만, **회원가입한 계정과 일반 사용자가 실제로 넣은 주문은 사라집니다.** |
| **Render PostgreSQL** | 주문 · 계정 유지 | Render에서 PostgreSQL 생성 → Internal URL을 `DATABASE_URL`에 등록. 무료 PostgreSQL은 사용 기한이 있으니 Render 요금 안내를 확인하세요. |

> `config.py`에서 `DATABASE_URL`이 `postgres://`로 시작하면 `postgresql://`로 바꿔서 SQLAlchemy에 넘깁니다.

### `render.yaml` (선택)

```yaml
services:
  - type: web
    name: aldicom-us-website
    runtime: python
    branch: main
    buildCommand: pip install -r requirements.txt
    startCommand: flask --app app:create_app setup-db && gunicorn -w 2 -b 0.0.0.0:$PORT "app:create_app()"
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: FLASK_DEBUG
        value: "0"
      - key: ADMIN_EMAIL
        sync: false
      - key: ADMIN_PASSWORD
        sync: false
      - key: CUSTOMER_EMAIL
        sync: false
      - key: CUSTOMER_PASSWORD
        sync: false
      - key: DATABASE_URL
        sync: false
```

### 배포 체크리스트

- [ ] `SECRET_KEY` 운영용 값, `FLASK_DEBUG=0`
- [ ] 계정 4개 환경 변수 등록 → 관리자 · 일반 사용자 로그인 확인
- [ ] 비로그인으로 모든 소개 페이지 접근 가능 확인
- [ ] 비로그인 장바구니 담기 → 로그인 → 원래 페이지 복귀 확인
- [ ] 일반 사용자로 `/admin/` 접근 시 403 확인
- [ ] 로그아웃 후 `/shop/cart`, `/admin/` 접근 시 로그인 페이지로 이동 확인
- [ ] `/r/<code>` → 주문 → 링크별 CSV에 반영 확인
- [ ] CSV 3종 엑셀에서 한글 · 숫자 깨짐 없음, 더미 기준 제품 · 링크 각 100건 이상 확인
- [ ] 404 · 403 · 500 에러 페이지, 모바일 메뉴 확인
- [ ] 사이트 카피 규제 문구 점검 (§20)

---

## 19. 개발 로드맵

| 단계 | 담당 | 범위 | 완료 기준 |
|---|---|---|---|
| **Phase 0** 기반 | A | 프로젝트 세팅, `extensions.py` · `cli.py`, 빈 Blueprint 전체, `base.html` · 헤더 · 푸터, **로그인 · 로그아웃 · 계정 시드**, Render 첫 배포 | 배포 URL에서 모든 탭 이동, 두 계정 로그인 · 로그아웃 |
| **Phase 1** 구매 · 데이터 | B → C | `shop` 모델 · **더미 1,000건 시드**, 제품 목록 · 상세, 장바구니 · 주문 · 내 주문, `/r/<code>` / 관리자 대시보드 · **CSV 3종** | 일반 사용자 주문 완료, 관리자 CSV 다운로드 |
| **Phase 2** 콘텐츠 | A · C | Home 전 섹션, About, Where to Buy, Vibe Test, Feed, Creators, Contact | 전 페이지 콘텐츠 채움 |
| **Phase 3** 마감 | 전원 | 이미지 교체, 관리자 링크 등록 화면, 반응형 · SEO, 규제 · 보안 점검 | 배포 체크리스트 완료 |

---

## 20. 카피 · 규제 · 보안 유의사항

### 카피 · 규제

> 이 사이트 문구는 법률 자문을 거친 것이 아닙니다. **공개 전 법무 검토를 권장합니다.**

- FDA는 숙취 증상의 예방 · 치료 · 완화 주장을 **질병 주장**으로 볼 수 있습니다. (FDA, 2020.07 숙취 제품 경고장)
- 사이트 전체(제품 설명, 장바구니 · 주문 화면, Feed, Vibe Test 결과, 이미지 속 문구, 메타 태그)에 아래 표현을 쓰지 않습니다.

| ❌ 쓰지 않을 표현 (예) | 이유 |
|---|---|
| prevents / cures / treats / relieves hangover | 질병 예방 · 치료 주장 |
| hangover cure, hangover remedy, anti-hangover | 같은 의미 |
| detox, flushes alcohol, sober up faster | 효능 · 생리 작용 주장 |
| drink more, drink without worry | 과음 조장 |

- Balance 2종(Jelly Balance, Drink Balance)은 **Zero Sugar**로 표기합니다. (표기 조건을 충족했다고 가정, Original 2종에는 쓰지 않음)
- 성분(A-HAT, 헛개나무 열매)은 **원료 소개**까지만 하고 효능과 연결하지 않습니다.
- 미성년자를 연상시키는 이미지 · 표현을 쓰지 않습니다.
- Creators 페이지에는 협업 시 금지 표현 안내를 둡니다. (FTC 보증 가이드상 크리에이터 발언도 브랜드 책임) 인플루언서 전용 링크 게시물에는 협찬 표시(#ad 등)를 안내합니다.
- 가격은 **가상값**이며 화면에 표시합니다. 결제는 모의 결제입니다.

### 보안

- 비밀번호는 해시로만 저장, 평문 로그 출력 금지
- 모든 POST 폼(로그인 · 로그아웃 · 장바구니 · 주문 · 문의)에 CSRF 토큰
- 로그인 후 `next` 이동은 **같은 사이트 상대 경로만** 허용 (오픈 리다이렉트 방지)
- 가격 · 할인은 서버에서만 계산
- `/admin/*` 전부 `@admin_required`, CSV 수식 주입 방지 (§8)
- 더미 데이터의 이름 · 주소 · 인플루언서는 모두 가상이며 실존 인물 · 계정과 무관합니다.

---

## 21. 회의 메모

### 2026-10-23

#### 홈페이지 제작 시 주의사항 `[06:00~07:13]`

- 홈페이지를 만들 때 자율성을 주고 만들어 달라고 하면 더 미감 좋게 만들어줌
- 홈페이지를 먼저 만들어 두고, 게임을 구현할 수 있으면 그때 집어넣는 건 어떨지 좋게 생각함
- 홈페이지를 만들 때는 프로덕트 4개, 피드, 게임으로 하면 될 것 같음

#### 노션 아이디 업로드 `[07:16~09:01]`

- 노션 아이디 업로드 해 줬는지 확인하고 깃허브 아이디도 함께 적어달라고 함
- 기획서만 쓰면 내가 돌릴 테니 언니는 기톡 아이디를 알려달라고 함

#### 바탕 화면 설정

- 유저 안에 있으면 신뢰가 되는 건데 베타가 한 명 있으면 신뢰를 우선 물어봐 줘야 함
- 시드라이브에 있으면 그런 거 안 물어봄
- 바탕 화면을 만들어야 하는데 하고 아니면 그냥 옮기면 됨
