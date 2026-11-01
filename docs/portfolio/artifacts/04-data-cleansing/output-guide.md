# 4. 데이터 클렌징 — 산출물 설명

한글 컬럼을 표준 이름으로 매핑하고 필수값·날짜·금액·중복을 검사합니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/column_mapping.py)

[입력 XLSX](../../../../data/demo/portfolio_artifacts/04-data-cleansing/input.xlsx) · [출력 XLSX](../../../../data/demo/portfolio_artifacts/04-data-cleansing/output.xlsx)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 분석 전 자료 품질 진단 |
| 파일에서 확인한 상태 | 매핑·품질 검사 · 날짜 설정 오류 |
| 조건·입력 | 필수 Journal_ID, GL_Account_Number, Effective_Date, Amount, Entered_By / 날짜 Effective_Date / 금액 Amount(사용자 요청). |

## 입력 구조

| 시트 | 컬럼 |
| --- | --- |
| cleansing_raw | `전표번호`, `계정번호`, `거래일자`, `금액`, `입력자` |
| cleansing_mapping | `Source_Field`, `Target_Field` |

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| duplicate_rows | 중복 집합에 속한 원본 행 1건 |
| field_profile | 컬럼 1개의 품질 요약 |
| issues | 필드·행별 품질 문제 1건 |
| mapped_data | 표준 컬럼명으로 매핑한 원본 행 1건 |
| mapping_suggestions | 표준 컬럼 1개의 매핑 후보 |

### `duplicate_rows` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Journal_ID` | VARCHAR | 전표 식별자 |
| `GL_Account_Number` | VARCHAR | 계정코드 |
| `Effective_Date` | DATE | 회계 반영일 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `Entered_By` | VARCHAR | 입력 사용자 |

### `field_profile` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Field` | VARCHAR | 검사·프로파일 대상 컬럼 |
| `Row_Count` | INTEGER | 그룹 행 수 또는 프로파일 전체 행 수 |
| `Missing_Count` | INTEGER | 결측 행 수 |
| `Unique_Count` | INTEGER | 고유값 수 |

### `issues` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Code` | VARCHAR | 품질 검사 오류 코드 |
| `Field` | VARCHAR | 검사·프로파일 대상 컬럼 |
| `Source_Row` | INTEGER | 원본 논리 데이터 행 번호 |
| `Value` | TEXT | 문제가 된 원본 값 |
| `Message` | TEXT | 품질 문제 설명 |

### `mapped_data` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Journal_ID` | VARCHAR | 전표 식별자 |
| `GL_Account_Number` | VARCHAR | 계정코드 |
| `Effective_Date` | DATE | 회계 반영일 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `Entered_By` | VARCHAR | 입력 사용자 |

### `mapping_suggestions` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Target_Field` | VARCHAR | 표준 대상 컬럼명 |
| `Candidates` | JSON / TEXT | 매핑 후보 컬럼 목록 |
| `Status` | VARCHAR | 매핑·계산 등 표별 처리 상태 |
| `Suggested_Source` | VARCHAR | 추천 원본 컬럼 |

## 연결키와 집계

입력 cleansing_mapping의 Source_Field→Target_Field로 이름을 연결합니다. issues.Source_Row는 원본 엑셀 행이며 Field는 표준 컬럼입니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

출력에는 필수값 결측, 금액 오류와 `Effevtive_Date` 컬럼 부재가 기록되어 있습니다. 요청의 Effective_Date와 출력 설정명이 달라 날짜 검사는 설정 재확인 대상입니다. mapped_data에는 오류·중복이 보존되며 수정 전 검토 자료로 제공합니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
