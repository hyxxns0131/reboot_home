# 재고 CSV 업로드 테스트 파일

관리자 › **Inventory(재고 관리)** › **CSV UPLOAD**에서 직접 올려 보는 테스트용 파일입니다.
"on_hand means"에서 **모드**를 아래 표대로 고른 뒤 올리세요.

- **New count (stocktake)** = 파일의 on_hand가 새 재고 수량이 됨 (재고 실사)
- **Add to stock (delivery received)** = 파일의 on_hand만큼 더하거나 뺌 (입고 · 파손 · 반품 조정)
- 한 줄이라도 틀리면 **아무것도 바뀌지 않고**, 빨간 메시지에 몇 번째 줄이 왜 틀렸는지 나옵니다.

## 시작 상태 (더미 기초 재고 · `flask setup-db` 직후)

| SKU | 재고 | 재주문 기준 |
|---|---:|---:|
| jelly-original-pouch | 351 | 40 |
| jelly-balance-pouch | 35 (부족) | 40 |
| drink-original-box3 | 358 | 25 |
| drink-original-lemon | 351 | 40 |
| drink-original-lime | 380 | 40 |
| drink-original-cherry | 420 | 40 |
| drink-balance-box3 | 217 | 25 |
| drink-balance-lemon | 214 | 40 |
| drink-balance-lime | 382 | 40 |
| drink-balance-cherry | 18 (부족) | 40 |

> 처음 상태로 돌리려면 로컬에서 `flask --app app:create_app reset-db` (FLASK_DEBUG=1일 때만).

## ✅ 성공해야 하는 파일 (01 → 06 순서대로 올리면 아래 숫자가 나옵니다)

| 파일 | 모드 | 무엇을 확인하나 | 결과 |
|---|---|---|---|
| `01_stocktake_full.csv` | New count | 관리자에서 내려받은 형식 그대로 (sku · product · option · on_hand · reorder_level, 상품명에 쉼표 포함) | 10개 옵션 모두 변경 → 예: jelly-original 320, drink-balance-cherry 12 |
| `02_stocktake_partial.csv` | New count | 일부 SKU만 (`sku, on_hand` 두 열) — 나머지는 그대로 | lemon 300 · lime 295 · cherry 410(이미 410이라 변화 없음) |
| `03_delivery_received.csv` | Add to stock | 입고 + 재주문 기준 같이 바꾸기, reorder_level 빈칸은 그대로 | jelly-balance 30→**330**(기준 60), drink-balance-cherry 12→**252**(기준 60), drink-balance-lemon +120, drink-original-box3 +96 |
| `04_adjust_damaged_returns.csv` | Add to stock | 음수로 빼기(파손) · 양수(반품) · 모르는 열(`note`)은 무시 | box3 −2, drink-balance-lime −5, jelly-original +4 |
| `05_excel_utf8_bom_crlf.csv` | New count | 엑셀 "CSV UTF-8" 저장 형식: BOM, Windows 줄바꿈, 대문자 · 공백 섞인 열 이름, 값 앞뒤 공백, 빈 줄 | jelly-original 300(기준 50), drink-balance-box3 220(기준 30) |
| `06_extra_columns_any_order.csv` | New count | 열 순서가 뒤섞이고 다른 열(창고 · 담당자 · 메모)이 있어도 sku · on_hand · reorder_level만 읽음 | jelly-balance 150, drink-balance-box3 260, drink-balance-lemon 188 |

재고 화면 아래 **STOCK LOG**에 줄마다 `CSV · new count` / `CSV · added`와 파일 이름이 남는지도 확인하세요.

## ❌ 막혀야 하는 파일 (올려도 재고가 하나도 바뀌지 않아야 정상)

| 파일 | 모드 | 일부러 넣은 오류 | 나와야 하는 메시지 |
|---|---|---|---|
| `11_error_unknown_sku.csv` | New count | 오타 SKU · 없는 맛(peach) | Row 3: unknown SKU "drink-orignal-lemon" · Row 4: unknown SKU "drink-original-peach" |
| `12_error_not_numbers.csv` | New count | `1,200` · `12.5` · `abc` · reorder `ten` | 줄마다 "… is not a whole number" (쉼표면 "remove the comma") |
| `13_error_negative_stocktake.csv` | New count | 재고 실사에 −5 | a stock count can't be negative (use "Add to stock" …) |
| `14_error_duplicate_sku.csv` | New count | 같은 SKU 두 번 | Row 3: drink-balance-lime appears twice |
| `15_error_missing_columns.csv` | New count | 열 이름이 `item, qty` | The file needs the columns sku and on_hand |
| `16_error_header_only.csv` | New count | 머리줄만 있고 내용 없음 | The file has no rows. |
| `17_error_delivery_below_zero.csv` | **Add to stock** | 재고보다 많이 빼기(−500) | drink-balance-cherry: stock would go below 0 (… on hand −500) |
| `18_error_korean_excel_cp949.csv` | New count | 한글 엑셀 기본 저장(CP949) | This file is not UTF-8. In Excel choose File › Save As › "CSV UTF-8" … |
| `19_error_too_big.csv` | New count | 재고 250,000 · 재주문 기준 −1 | over the 100,000 limit · reorder_level −1 must be 0–100,000 |
| `20_error_not_a_csv.txt` | 아무거나 | 확장자가 .txt | Choose a .csv file. (파일 선택 창에서 "모든 파일"로 바꿔야 고를 수 있음) |

## 직접 만들 때

- 필요한 열: `sku`, `on_hand` (+ 선택 `reorder_level`). 열 이름은 대소문자 · 순서 상관없음.
- 가장 쉬운 방법: 재고 화면의 **Current inventory / template ↓ CSV**를 받아 숫자만 고쳐서 다시 올리기.
- 엑셀에서 저장할 때는 꼭 **CSV UTF-8 (쉼표로 분리)**. 숫자에 천 단위 쉼표(1,200)를 넣지 않기.
