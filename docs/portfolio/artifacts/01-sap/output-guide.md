# 1. SAP 전처리 — 산출물 설명

전표 상세·헤더·계정잔액을 GL·TB로 변환하고 연결·금액을 검사합니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/sap.py)

[입력 XLSX](../../../../data/demo/portfolio_artifacts/01-sap/input.xlsx) · [출력 CSV](../../../../data/demo/portfolio_artifacts/01-sap/output.csv)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 분석 자료 표준화와 모집단 연결 확인 |
| 파일에서 확인한 상태 | 입력 범위 오류 · 변환 미실행 |
| 조건·입력 | 회사 3000 / 회계연도 2007 / 원장 0 / 실적구분 0 / 버전 1. 설정은 사용자가 제공한 실행 조건입니다. |

## 입력 구조

| 시트 | 컬럼 |
| --- | --- |
| SAP_BKPF_전표헤더 | 파이프 구분 원본 92필드가 한 열에 저장 |
| SAP_BSEG_전표상세 | 87개 원본 필드 |
| SAP_GLT0_계정잔액 | 63개 원본 필드 |

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

BSEG와 BKPF는 회사·연도·전표번호로 연결하며 상세 항목번호가 추가 식별자입니다. GLT0는 회사·연도·원장·실적구분·버전으로 범위를 선택합니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

출력은 BSEG·BKPF·GLT0의 `EMPTY_SCOPE` 3건입니다. 변환 상태는 입력 검증 단계입니다. 제공 입력의 BKPF는 파이프(|) 구분 필드가 한 열에 들어 있으며, 원인 확인에는 파싱·업로드 조건을 함께 대조합니다. 원본 범위와 문자열·숫자 인식, 슬롯별 업로드를 확인합니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
