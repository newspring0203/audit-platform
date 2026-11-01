# 7. 총계정원장 테스트(JET) — 산출물 설명

규칙에 맞는 분개를 선정하고 전표별 검토 목록으로 묶습니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/jet.py)

[입력 XLSX](../../../../data/demo/portfolio_artifacts/07-jet/input.xlsx) · [출력 XLSX](../../../../data/demo/portfolio_artifacts/07-jet/output.xlsx)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 전표 검토 대상 선정과 로그 대사 |
| 파일에서 확인한 상태 | GL 규칙 선정 · 로그 대사 미실행 |
| 조건·입력 | 정액 1000 / 저빈도 사용자 10 / 저빈도 계정 3 / 복합 조건 최소 2(사용자 제공 설정). 저빈도는 실제 코드상 고유 전표 수입니다. |

## 입력 구조

| 시트 | 컬럼 |
| --- | --- |
| gl_jet | `Journal_ID`, `Journal_ID_Line_Number`, `GL_Account_Number`, `Business_Unit_Code`, `Fiscal_Year`, `Period`, `Amount`, `Amount_Currency`, `Amount_Credit_Debit_Indicator`, `Effective_Date`, `Entered_Date`, `Entered_Time`, `Entered_By`, `Source`, `JE_Line_Description`, `JE_Header_Description` |
| log_control | `Journal_ID`, `Amount_Currency`, `Amount_Credit_Debit_Indicator`, `Total` |

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| flagged_lines | 분개 항목×일치 규칙 1건 |
| journal_review_queue | 전표·통화별 검토 요약 1건 |
| log_basis_issues | 로그 대사 근거 문제 1건 |

### `flagged_lines` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Journal_ID` | VARCHAR | 전표 식별자 |
| `Journal_ID_Line_Number` | VARCHAR | 전표 내 상세 항목번호 |
| `GL_Account_Number` | VARCHAR | 계정코드 |
| `Business_Unit_Code` | VARCHAR | 사업단위 코드 |
| `Fiscal_Year` | VARCHAR | 회계연도 |
| `Period` | VARCHAR / DATE | 회계기간; 재고 월별 표에서는 연월 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Amount_Credit_Debit_Indicator` | CHAR(1) | 차변 D / 대변 C |
| `Effective_Date` | DATE | 회계 반영일 |
| `Entered_Date` | DATE | 입력일 |
| `Entered_Time` | TIME | 입력시간; HHMM/HHMMSS 해석 |
| `Entered_By` | VARCHAR | 입력 사용자 |
| `Source` | VARCHAR | 전표 원천 구분 |
| `JE_Line_Description` | TEXT | 분개 항목 적요 |
| `JE_Header_Description` | TEXT | 전표 헤더 적요 |
| `Source_Row` | INTEGER | 원본 논리 데이터 행 번호 |
| `Rule_ID` | VARCHAR | 일치한 선정 규칙 |
| `Selection_Reason` | TEXT | 분개 선정 사유 |
| `Suggested_Review` | TEXT | 후속 검토 사항 |

### `journal_review_queue` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Journal_ID` | VARCHAR | 전표 식별자 |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Matched_Rule_Count` | INTEGER | 전표별 고유 일치 규칙 수 |
| `Rules` | TEXT | 일치 규칙 목록 |
| `Complex_Condition` | BOOLEAN | 복합 규칙 최소 개수 충족 |
| `Debit_Total` | DECIMAL | 해당 전표·통화의 차변 합계 |
| `Credit_Total` | DECIMAL | 해당 전표·통화의 대변 합계 |
| `Selection_Reasons` | TEXT | 전표별 선정 사유 목록 |
| `Suggested_Review` | TEXT | 후속 검토 사항 |
| `Source_Rows` | TEXT | 연결된 원본 행 번호 목록 |

### `log_basis_issues` 데이터 사전

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

## 연결키와 집계

분개는 Journal_ID+항목번호, 검토 큐는 Journal_ID+통화로 연결합니다. flagged_lines는 분개×규칙이므로 같은 금액이 반복될 수 있습니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

로그 대사는 `BASIS_INFORMATION_MISSING` 상태입니다. GL 규칙 결과는 별도로 제공합니다. Matched_Rule_Count는 서로 다른 규칙 수입니다. 분개×규칙 표를 그대로 금액 합산하면 중복 집계됩니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
