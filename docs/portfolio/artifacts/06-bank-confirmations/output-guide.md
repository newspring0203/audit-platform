# 6. 금융기관 조회 회신 — 산출물 설명

은행 잔액과 금리·만기·담보·보증 등 계약조건을 비교합니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/confirmations.py)

[입력 XLSX](../../../../data/demo/portfolio_artifacts/06-bank-confirmations/input.xlsx) · [출력 CSV](../../../../data/demo/portfolio_artifacts/06-bank-confirmations/output.csv)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 금융계좌·차입 항목과 회신 조건 검토 |
| 파일에서 확인한 상태 | 기준일 오류 · 대사 미실행 |
| 조건·입력 | ledger·requests·replies와 분석 기준일·허용차이. 분석 기준일은 실행 설정과 대조합니다. |

## 입력 구조

| 시트 | 컬럼 |
| --- | --- |
| BANK_ledger | `Business_Unit_Code`, `Institution_ID`, `Account_ID`, `Item_Type`, `Currency`, `As_Of_Date`, `Balance`, `Interest_Rate`, `Maturity_Date`, `Collateral`, `Guarantees`, `Restrictions`, `Other_Arrangements` |
| BANK_requests | `Request_ID`, `Business_Unit_Code`, `Institution_ID`, `Account_ID`, `Item_Type`, `Currency`, `As_Of_Date` |
| BANK_replies | `Request_ID`, `Response_Status`, `Reply_As_Of_Date`, `Confirmed_Balance`, `Evidence_Reference`, `Interest_Rate`, `Maturity_Date`, `Collateral`, `Guarantees`, `Restrictions`, `Other_Arrangements`, `Business_Unit_Code`, `Institution_ID`, `Account_ID`, `Item_Type`, `Currency` |

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| validation_issues (CSV) | 검증 문제 1건 |

### `validation_issues (CSV)` 데이터 사전

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
| `suggested_review` | TEXT | 권장 확인·조치 |

## 연결키와 집계

장부↔요청: 사업단위·금융기관·계좌·항목유형·통화·기준일. 회신은 Request_ID로 연결하고 범위를 재확인합니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

출력은 `CONFIRMATION_DATE_SCOPE` 1건입니다. 계약조건 비교는 기준일 수정 후 재실행으로 확인합니다. 정상 실행에서는 금리·만기·담보·보증·제한·기타 약정을 문자열로 비교하며 값 일치와 원문 검토 완료를 구분합니다. 공란은 추가 확인 대상으로 해석합니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
