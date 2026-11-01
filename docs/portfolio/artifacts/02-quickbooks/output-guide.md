# 2. QuickBooks 전처리 — 산출물 설명

계정 제목·거래·합계가 섞인 보고서를 계정명이 붙은 거래 표로 펼칩니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/quickbooks.py)

[입력 CSV](../../../../data/demo/portfolio_artifacts/02-quickbooks/input.csv) · [출력 XLSX](../../../../data/demo/portfolio_artifacts/02-quickbooks/output.xlsx)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 거래 데이터 준비와 행 처리 이력 확인 |
| 파일에서 확인한 상태 | 평탄화 결과 · ADS 미변환 |
| 조건·입력 | 입력 보고서 형식과 날짜 형식을 확인합니다. 현재 제공 CSV는 9열이며 엔진의 지원 형식인 13열과 다릅니다. |

## 입력 구조

`(무명 컬럼)`, `Type`, `Date`, `Num`, `Name`, `Memo`, `Split`, `Amount`, `Balance`

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| modified_gl | 계정 제목이 붙은 거래 1건 |
| row_dispositions | 원본 보고서 행 1건의 분류 |

### `modified_gl` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `QuickBooks_Source_Row` | INTEGER | 원본 보고서 행 번호 |
| `Account_Source_Row` | INTEGER | 계정 제목 원본 행 번호 |
| `Account Description` | TEXT | 거래에 연결한 계정 제목 |
| `Type` | VARCHAR | 거래 유형 |
| `Date` | DATE | 거래일 |
| `Num` | VARCHAR | 문서·거래 번호; 앞자리 0 보존 |
| `Name` | TEXT | 거래 상대방 |
| `Memo` | TEXT | 적요 |
| `Split` | TEXT | 상대계정 등 보고서 표시 |
| `Amount` | DECIMAL | 금액; 통화·부호 정의는 표별 확인 |
| `Balance` | DECIMAL | 원본 보고서 잔액 |
| `Conversion_Status` | VARCHAR | 평탄화 수행 상태 |
| `ADS_Status` | VARCHAR | ADS 변환 상태 |

### `row_dispositions` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `QuickBooks_Source_Row` | INTEGER | 원본 보고서 행 번호 |
| `Row_Type` | VARCHAR | 헤더·계정 제목·거래·합계 등 분류 |
| `Reason` | TEXT | 분류·검토·계산 상태의 사유 |

## 연결키와 집계

`QuickBooks_Source_Row`는 거래 원본 행, `Account_Source_Row`는 계정 제목 원본 행입니다. 처리 이력의 같은 원본 행 번호로 연결합니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

출력에는 completed_flattening / not_converted가 기록되어 있습니다. 현재 CSV 사본에는 보고서의 빈 표시 열이 줄어들어 있어 그대로 재실행하면 지원 레이아웃 검증에 걸릴 수 있습니다. 제공 파일의 관찰 결과와 재실행 성공을 구분합니다. 문서번호는 문자열로 관리해 앞자리 0을 보존합니다. row_dispositions에는 데이터 외 설명/서식 영역이 있을 수 있습니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
