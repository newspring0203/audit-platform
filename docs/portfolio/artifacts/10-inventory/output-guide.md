# 10. 재고 수불 분석 — 산출물 설명

기초·입출고로 재고수량을 계산하고 음수·장기 미출고 후보를 찾습니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/inventory.py)

[입력 XLSX](../../../../data/demo/portfolio_artifacts/10-inventory/input.xlsx) · [출력 XLSX](../../../../data/demo/portfolio_artifacts/10-inventory/output.xlsx)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 재고 수량 흐름과 추가 확인 대상 파악 |
| 파일에서 확인한 상태 | 수불 분석 · 로트 기준일 오류 |
| 조건·입력 | movements·opening·lot_snapshot과 분석 기준일·장기 미출고 기준. 실행 기준일·설정은 작업 조건에서 확인합니다. |

## 입력 구조

| 시트 | 컬럼 |
| --- | --- |
| movements | `Item_ID`, `Date`, `Quantity_In`, `Quantity_Out` |
| opening | `Item_ID`, `Opening_Quantity` |
| lot_snapshot | `Item_ID`, `Lot_ID`, `Receipt_Date`, `Snapshot_Date`, `Remaining_Quantity` |

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| item_summary | 품목별 수불·기말·검토 요약 |
| module_issues | 분석 실행 이슈 1건 |
| monthly_movements | GL의 계정·연도·기간별 순변동 또는 재고의 품목·월별 입출고 |
| movement_timeline | 수불 기록 1건과 누적수량 |
| negative_events | 누적수량이 음수인 수불 기록 1건 |
| review_items | 기능별 후속 검토 대상 1건 |

### `item_summary` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Item_ID` | VARCHAR | 품목 ID |
| `Opening_Quantity` | DECIMAL | 명시적 기초수량 |
| `Quantity_In` | DECIMAL | 입고수량 |
| `Quantity_Out` | DECIMAL | 출고수량 |
| `Last_Out_Date` | DATE | 제출 수불 내 마지막 출고일 |
| `Days_Since_Last_Out` | INTEGER | 분석 기준일까지 마지막 출고 후 경과일 |
| `No_Outflow_In_Data` | BOOLEAN | 제출 범위 내 출고 이력 없음 |
| `Ending_Quantity` | DECIMAL | 기초+입고−출고 기말수량 |
| `Negative_Stock` | BOOLEAN | 기말수량 음수 |
| `Stale_Candidate` | BOOLEAN | 장기 미출고 후보 |
| `Review_Required` | BOOLEAN | 검토 대상 표시 |

### `module_issues` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `code` | VARCHAR | 검증·실행 오류 코드 |
| `field` | VARCHAR | 검사 대상 필드 |
| `message` | TEXT | 문제 설명 |
| `source_table` | VARCHAR | 문제의 원본 테이블 |
| `source_file` | TEXT | 원본 파일·입력 슬롯 |
| `source_row` | INTEGER | 원본 논리 행 번호 |
| `source_field` | VARCHAR | 원본 컬럼 |
| `value` | TEXT | 문제가 된 원본 값 |
| `journal_id` | VARCHAR | 관련 전표 ID |
| `severity` | VARCHAR | 이슈 심각도 |

### `monthly_movements` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Item_ID` | VARCHAR | 품목 ID |
| `Period` | DATE / VARCHAR | 수불을 집계한 연월; Excel에서는 날짜값으로 표시될 수 있음 |
| `Quantity_In` | DECIMAL | 입고수량 |
| `Quantity_Out` | DECIMAL | 출고수량 |
| `Net_Quantity` | DECIMAL | 입고−출고 |

### `movement_timeline` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Item_ID` | VARCHAR | 품목 ID |
| `Date` | DATE | 거래일 |
| `Quantity_In` | DECIMAL | 입고수량 |
| `Quantity_Out` | DECIMAL | 출고수량 |
| `Source_Row` | INTEGER | 원본 논리 데이터 행 번호 |
| `Net_Quantity` | DECIMAL | 입고−출고 |
| `Running_Quantity` | DECIMAL | 기초+해당 행까지 누적 순입고 |

### `negative_events` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Item_ID` | VARCHAR | 품목 ID |
| `Date` | DATE | 거래일 |
| `Quantity_In` | DECIMAL | 입고수량 |
| `Quantity_Out` | DECIMAL | 출고수량 |
| `Source_Row` | INTEGER | 원본 논리 데이터 행 번호 |
| `Net_Quantity` | DECIMAL | 입고−출고 |
| `Running_Quantity` | DECIMAL | 기초+해당 행까지 누적 순입고 |
| `Review_Reason` | TEXT | 추가 확인 사유 |

### `review_items` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Item_ID` | VARCHAR | 품목 ID |
| `Opening_Quantity` | DECIMAL | 명시적 기초수량 |
| `Quantity_In` | DECIMAL | 입고수량 |
| `Quantity_Out` | DECIMAL | 출고수량 |
| `Last_Out_Date` | DATE | 제출 수불 내 마지막 출고일 |
| `Days_Since_Last_Out` | INTEGER | 분석 기준일까지 마지막 출고 후 경과일 |
| `No_Outflow_In_Data` | BOOLEAN | 제출 범위 내 출고 이력 없음 |
| `Ending_Quantity` | DECIMAL | 기초+입고−출고 기말수량 |
| `Negative_Stock` | BOOLEAN | 기말수량 음수 |
| `Stale_Candidate` | BOOLEAN | 장기 미출고 후보 |
| `Review_Required` | BOOLEAN | 검토 대상 표시 |

## 연결키와 집계

Item_ID로 기초와 수불 집계를 연결하고 품목+로트로 로트 명세를 식별합니다. Source_Row로 수불 원본 위치를 추적합니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

`LOT_SNAPSHOT_DATE_MISMATCH`가 기록되어 로트 분석은 미실행입니다. item_summary는 기말, negative_events는 기간 중 음수 시점입니다. 같은 날짜의 수불은 원본 행 순서로 계산합니다. 기초 누락은 실제 엔진에서 MISSING_OPENING으로 차단합니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
