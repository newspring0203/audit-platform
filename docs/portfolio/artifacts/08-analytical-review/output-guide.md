# 8. 분석적 검토 — 산출물 설명

전기·당기 계정 순변동과 시점 잔액을 비교하고 재무비율을 계산합니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/analytics.py)

[입력 XLSX](../../../../data/demo/portfolio_artifacts/08-analytical-review/input.xlsx) · [출력 XLSX](../../../../data/demo/portfolio_artifacts/08-analytical-review/output.xlsx)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 계정 변동·추세와 후속 확인 대상 파악 |
| 파일에서 확인한 상태 | 기간 비교·잔액·재무비율 초안 |
| 조건·입력 | 당기 2026 / 전기 2025 / 증감률 30% / TB 비교 기간 10 / 차변 양수·대변 음수 확인(사용자 제공 설정). |

## 입력 구조

| 시트 | 컬럼 |
| --- | --- |
| gl_comparison | `Journal_ID`, `Journal_ID_Line_Number`, `GL_Account_Number`, `Business_Unit_Code`, `Fiscal_Year`, `Period`, `Amount`, `Amount_Currency`, `Amount_Credit_Debit_Indicator`, `Effective_Date`, `Entered_Date`, `Entered_Time`, `Entered_By`, `Source`, `JE_Line_Description`, `JE_Header_Description` |
| tb | `Business_Unit_Code`, `GL_Account_Number`, `Fiscal_Year`, `Period`, `Amount_Currency`, `Amount_Ending` |
| account_mapping | `Business_Unit_Code`, `GL_Account_Number`, `Metric_Group`, `Sign_Multiplier` |

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| balance_comparison | 사업단위·계정·통화별 TB 연도 비교 |
| financial_ratios | 사업단위·연도·통화·지표별 계산 1건 |
| monthly_comparison | 사업단위·계정·통화·기간별 연도 비교 |
| monthly_movements | GL의 계정·연도·기간별 순변동 또는 재고의 품목·월별 입출고 |
| year_comparison | 사업단위·계정·통화별 관측 연도 순변동 비교 |
| period_coverage | 연도별 관측 기간 목록 |
| ratio_components | 사업단위·연도·통화·재무 분류별 합계 |

### `balance_comparison` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Business_Unit_Code` | VARCHAR | 사업단위 코드 |
| `GL_Account_Number` | VARCHAR | 계정코드 |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Current_Cents` | BIGINT | 당기 금액의 100배 정수 |
| `Prior_Cents` | BIGINT | 전기 금액의 100배 정수 |
| `Presence` | VARCHAR | 당기·전기 자료 존재 구분 |
| `Current_Balance` | DECIMAL | 선택 TB 기간의 당기 잔액 |
| `Prior_Balance` | DECIMAL | 선택 TB 기간의 전기 잔액 |
| `Balance_Change` | DECIMAL | 당기 잔액−전기 잔액 |
| `Balance_Change_Pct` | DECIMAL | 잔액 증감률; 75는 75% |

### `financial_ratios` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Business_Unit_Code` | VARCHAR | 사업단위 코드 |
| `Fiscal_Year` | VARCHAR | 회계연도 |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Metric` | VARCHAR | 재무지표 이름 |
| `Value` | DECIMAL | 지표 계산값; Unit과 함께 해석 |
| `Unit` | VARCHAR | 배수·통화 등 지표 단위 |
| `Status` | VARCHAR | 매핑·계산 등 표별 처리 상태 |
| `Reason` | TEXT | 분류·검토·계산 상태의 사유 |

### `monthly_comparison` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Business_Unit_Code` | VARCHAR | 사업단위 코드 |
| `GL_Account_Number` | VARCHAR | 계정코드 |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Period` | VARCHAR / DATE | 회계기간; 재고 월별 표에서는 연월 |
| `Current_Cents` | BIGINT | 당기 금액의 100배 정수 |
| `Prior_Cents` | BIGINT | 전기 금액의 100배 정수 |
| `Presence` | VARCHAR | 당기·전기 자료 존재 구분 |
| `Current_Movement` | DECIMAL | 당기 GL 순변동 |
| `Prior_Movement` | DECIMAL | 전기 GL 순변동 |
| `Change` | DECIMAL | 당기−전기 순변동 |
| `Change_Pct` | DECIMAL | 순변동 증감률; 분모는 abs(전기) |

### `monthly_movements` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Business_Unit_Code` | VARCHAR | 사업단위 코드 |
| `GL_Account_Number` | VARCHAR | 계정코드 |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Fiscal_Year` | VARCHAR | 회계연도 |
| `Period` | VARCHAR / DATE | 회계기간; 재고 월별 표에서는 연월 |
| `Movement_Cents` | BIGINT | 순변동 금액의 100배 정수 |
| `Movement` | DECIMAL | GL 차변−대변 순변동 |

### `year_comparison` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Business_Unit_Code` | VARCHAR | 사업단위 코드 |
| `GL_Account_Number` | VARCHAR | 계정코드 |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Current_Cents` | BIGINT | 당기 금액의 100배 정수 |
| `Prior_Cents` | BIGINT | 전기 금액의 100배 정수 |
| `Presence` | VARCHAR | 당기·전기 자료 존재 구분 |
| `Current_Movement` | DECIMAL | 당기 GL 순변동 |
| `Prior_Movement` | DECIMAL | 전기 GL 순변동 |
| `Change` | DECIMAL | 당기−전기 순변동 |
| `Change_Pct` | DECIMAL | 순변동 증감률; 분모는 abs(전기) |
| `Review_Required` | BOOLEAN | 검토 대상 표시 |
| `Reason` | TEXT | 분류·검토·계산 상태의 사유 |

### `period_coverage` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Fiscal_Year` | VARCHAR | 회계연도 |
| `Observed_Periods` | TEXT | 실제 관측된 회계기간 목록 |

### `ratio_components` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Business_Unit_Code` | VARCHAR | 사업단위 코드 |
| `Fiscal_Year` | VARCHAR | 회계연도 |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Metric_Group` | VARCHAR | 재무비율 계산용 계정 분류 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |

## 연결키와 집계

GL: 사업단위·계정·통화·연도·기간으로 집계. TB→account_mapping은 사업단위+계정으로 연결합니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

GL 비교는 제공된 관측 기간의 순변동이며 period_coverage에서 범위를 확인합니다. TB 기간 10은 TB 선택 조건입니다. Change_Pct의 75는 75%이며 비율 단위를 확인합니다. financial_ratios는 calculated_draft 상태입니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
