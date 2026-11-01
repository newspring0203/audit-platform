# 3. 입력 사용자별 GL 분할 — 산출물 설명

총계정원장 행을 입력 사용자별로 나누고 원본 위치를 남깁니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/gl_split.py)

[입력 CSV](../../../../data/demo/portfolio_artifacts/03-gl-user-split/input.csv) · [출력 XLSX](../../../../data/demo/portfolio_artifacts/03-gl-user-split/output.xlsx)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 사용자별 자료 배분과 후속 거래 검토 |
| 파일에서 확인한 상태 | 그룹 목록·원본 연결·한 그룹 상세 |
| 조건·입력 | 입력 사용자 컬럼 Entered_By / 최대 그룹 수 500(사용자 제공 설정). |

## 입력 구조

`Review_Record_ID`, `Journal_ID`, `Journal_ID_Line_Number`, `JE_Header_Description`, `JE_Line_Description`, `Source`, `Business_Unit_Code`, `Effective_Date`, `Fiscal_Year`, `Period`, `GL_Account_Number`, `Amount`, `Amount_Credit_Debit_Indicator`, `Amount_Currency`, `Entered_By`, `Entered_Date`, `Entered_Time`, `Reversal_Indicator`

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| group_index | 사용자 그룹 1개 |
| row_membership | 원본 행 1건의 그룹 배정 |
| user_0001 | 해당 사용자에게 배정된 원장 행 1건 |

### `group_index` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Group_ID` | VARCHAR | 사용자 분할 그룹 ID |
| `Entered_By` | VARCHAR | 입력 사용자 |
| `User_Column` | VARCHAR | 분할 기준 컬럼명 |
| `User_Status` | VARCHAR | 입력 사용자 확보 상태 |
| `Row_Count` | INTEGER | 그룹 행 수 또는 프로파일 전체 행 수 |
| `Output_File` | TEXT | 그룹 출력 파일명; 파일 존재는 별도 확인 |

### `row_membership` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Group_ID` | VARCHAR | 사용자 분할 그룹 ID |
| `Source_Row` | INTEGER | 원본 논리 데이터 행 번호 |

### `user_0001` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Split_Source_Row` | INTEGER | 분할 전 GL 원본 행 번호 |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Journal_ID` | VARCHAR | 전표 식별자 |
| `Journal_ID_Line_Number` | VARCHAR | 전표 내 상세 항목번호 |
| `JE_Header_Description` | TEXT | 전표 헤더 적요 |
| `JE_Line_Description` | TEXT | 분개 항목 적요 |
| `Source` | VARCHAR | 전표 원천 구분 |
| `Business_Unit_Code` | VARCHAR | 사업단위 코드 |
| `Effective_Date` | DATE | 회계 반영일 |
| `Fiscal_Year` | VARCHAR | 회계연도 |
| `Period` | VARCHAR / DATE | 회계기간; 재고 월별 표에서는 연월 |
| `GL_Account_Number` | VARCHAR | 계정코드 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `Amount_Credit_Debit_Indicator` | CHAR(1) | 차변 D / 대변 C |
| `Amount_Currency` | VARCHAR | 금액 통화 |
| `Entered_By` | VARCHAR | 입력 사용자 |
| `Entered_Date` | DATE | 입력일 |
| `Entered_Time` | TIME | 입력시간; HHMM/HHMMSS 해석 |
| `Reversal_Indicator` | VARCHAR | 역분개 표시; 값 미확보 가능 |

## 연결키와 집계

`group_index.Group_ID → row_membership.Group_ID`는 1:N입니다. 사용자 표의 Split_Source_Row와 연결표의 Source_Row로 원본 위치를 추적합니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

첨부 XLSX에는 23개 그룹 목록과 user_0001 상세만 있습니다. 그룹별 CSV는 별도 파일 목록에서 확인합니다. 사용자별 행 분할이므로 전표가 여러 그룹에 걸칠 수 있습니다. 파일은 Excel 표시·형변환의 영향을 포함할 수 있어 원본 값 보존은 버전 비교로 확인합니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
