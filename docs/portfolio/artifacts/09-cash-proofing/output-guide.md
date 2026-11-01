# 9. 자금 대사 — 산출물 설명

은행 거래와 현금 원장을 비교해 연결·미대사·중복 후보를 구분합니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/cash.py)

[입력 XLSX](../../../../data/demo/portfolio_artifacts/09-cash-proofing/input.xlsx) · [출력 XLSX](../../../../data/demo/portfolio_artifacts/09-cash-proofing/output.xlsx)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 은행·장부 기록과 조정 항목 검토 |
| 파일에서 확인한 상태 | 거래 대사 · 잔액 기준일 오류 |
| 조건·입력 | bank·cash_gl·balances. 날짜 허용차이·기준일·장기 미대사 기준의 실행 설정은 별도 작업 조건에서 확인합니다. |

## 입력 구조

| 시트 | 컬럼 |
| --- | --- |
| bank | `Row_ID`, `Bank_Account`, `Currency`, `Date`, `Amount` |
| cash_gl | `Row_ID`, `Bank_Account`, `Currency`, `Date`, `Amount` |
| balances | `Bank_Account`, `Currency`, `As_Of_Date`, `Bank_Balance`, `GL_Balance`, `Bank_Adjustment`, `Adjustment_Reference` |

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| candidate_links | 은행·장부 거래 연결 후보 1쌍 |
| matches | 상호 유일 연결 1쌍 |
| module_issues | 분석 실행 이슈 1건 |
| review_items | 기능별 후속 검토 대상 1건 |
| unmatched_bank | 미대사 은행 거래 1건 |
| unmatched_gl | 미대사 장부 거래 1건 |

### `candidate_links` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Row_ID_Bank` | VARCHAR | bank.Row_ID 참조 |
| `Row_ID_GL` | VARCHAR | cash_gl.Row_ID 참조 |
| `Bank_Account` | VARCHAR | 은행계좌 식별자 |
| `Currency` | VARCHAR | 통화 |
| `Date_Bank` | DATE | 은행 거래일 |
| `Date_GL` | DATE | 장부 거래일 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `Date_Difference_Days` | INTEGER | 장부일−은행일 차이 |
| `Match_Basis` | TEXT | 후보 연결 근거 |
| `Candidate_Status` | VARCHAR | 유일·모호 후보 구분 |

### `matches` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Row_ID_Bank` | VARCHAR | bank.Row_ID 참조 |
| `Row_ID_GL` | VARCHAR | cash_gl.Row_ID 참조 |
| `Bank_Account` | VARCHAR | 은행계좌 식별자 |
| `Currency` | VARCHAR | 통화 |
| `Date_Bank` | DATE | 은행 거래일 |
| `Date_GL` | DATE | 장부 거래일 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `Date_Difference_Days` | INTEGER | 장부일−은행일 차이 |
| `Match_Basis` | TEXT | 후보 연결 근거 |
| `Candidate_Status` | VARCHAR | 유일·모호 후보 구분 |

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

### `review_items` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Side` | VARCHAR | Bank / GL 측 구분 |
| `Row_ID` | VARCHAR | 각 원본 자료 내 거래행 ID |
| `Source_Row` | INTEGER | 원본 논리 데이터 행 번호 |
| `Bank_Account` | VARCHAR | 은행계좌 식별자 |
| `Currency` | VARCHAR | 통화 |
| `Date` | DATE | 거래일 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `Candidate_Count` | INTEGER | 연결 후보 수 |
| `Days_Unmatched` | INTEGER | 기준일−거래일 경과일 |
| `Aged_Unmatched` | BOOLEAN | 장기 미대사 기준 충족 |
| `Review_Reason` | TEXT | 추가 확인 사유 |
| `Suggested_Review` | TEXT | 후속 검토 사항 |

### `unmatched_bank` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Row_ID` | VARCHAR | 각 원본 자료 내 거래행 ID |
| `Bank_Account` | VARCHAR | 은행계좌 식별자 |
| `Currency` | VARCHAR | 통화 |
| `Date` | DATE | 거래일 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `_amount_cents` | BIGINT | 부호 금액의 100배 정수 |
| `Source_Row` | INTEGER | 원본 논리 데이터 행 번호 |
| `Candidate_Count` | INTEGER | 연결 후보 수 |
| `Review_Reason` | TEXT | 추가 확인 사유 |
| `Days_Unmatched` | INTEGER | 기준일−거래일 경과일 |
| `Aged_Unmatched` | BOOLEAN | 장기 미대사 기준 충족 |

### `unmatched_gl` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Row_ID` | VARCHAR | 각 원본 자료 내 거래행 ID |
| `Bank_Account` | VARCHAR | 은행계좌 식별자 |
| `Currency` | VARCHAR | 통화 |
| `Date` | DATE | 거래일 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `_amount_cents` | BIGINT | 부호 금액의 100배 정수 |
| `Source_Row` | INTEGER | 원본 논리 데이터 행 번호 |
| `Candidate_Count` | INTEGER | 연결 후보 수 |
| `Review_Reason` | TEXT | 추가 확인 사유 |
| `Days_Unmatched` | INTEGER | 기준일−거래일 경과일 |
| `Aged_Unmatched` | BOOLEAN | 장기 미대사 기준 충족 |

## 연결키와 집계

candidate_links의 Row_ID_Bank→bank.Row_ID, Row_ID_GL→cash_gl.Row_ID. 계좌·통화·부호 금액·허용 시차 내 상호 유일 후보만 matches로 이동합니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

`BALANCE_DATE_MISMATCH`로 잔액 대사에는 제한이 있습니다. 금액 집계는 matches를 기준으로 수행합니다. review_items는 unmatched_bank/gl의 통합 검토 목록이므로 중복 집계를 피합니다. 잔액 대사식은 은행+조정−장부입니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
