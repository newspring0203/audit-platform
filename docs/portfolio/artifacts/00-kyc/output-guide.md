# 0. KYC 공시 — 산출물 설명

공시에서 검토할 문단을 찾아 출처·원문 위치·확인 질문을 연결합니다.

[전체 산출물](../../output-guide.md) · [프로젝트](../../../../README.md) · [구현 코드](../../../../src/audit_data_lab/kyc.py)

[출력 XLSX](../../../../data/demo/portfolio_artifacts/00-kyc/output.xlsx)

## 실행 요약

| 항목 | 내용 |
| --- | --- |
| 감사 흐름 | 기업·사업 이해와 후속 검토 자료 준비 |
| 파일에서 확인한 상태 | 문단 후보·출처 확보 |
| 조건·입력 | 회사·공시 기간·유형을 지정합니다. 파일 구성은 공시 수집 결과이며 조건은 실행 설정에서 관리합니다. |

## 입력 구조

회사·기간·공시 유형을 지정해 수집한 공시 기반 결과입니다.

## 출력 스키마

| 시트·표 | 한 행의 의미 |
| --- | --- |
| sources | 공시 문서 1건(추가 설명 행은 별도) |
| review_passages | 공시·주제별 문단 후보 1건 |

### `sources` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `source_id` | VARCHAR | 원본 공시 문서 ID; 해당 실행 내 키 후보 |
| `title` | TEXT | 공시 제목 |
| `url` | TEXT | 공시 원본 URL |
| `published_at` | DATE | 공시일; YYYYMMDD를 날짜로 변환 |
| `rcept_no` | VARCHAR | 공시 접수번호 |
| `corp_code` | VARCHAR | 기업코드; 앞자리 0 보존 |
| `corp_name` | VARCHAR | 기업명 |
| `document_sha256` | CHAR(64) | 수신 공시 ZIP 전체 바이트의 SHA-256 |
| `Document_Chars` | INTEGER | 추출 본문 문자 수 |

### `review_passages` 데이터 사전

| 컬럼 | DB 설계 시 타입 제안 | 의미 |
| --- | --- | --- |
| `Review_Record_ID` | VARCHAR | 실행·결과표·행 위치에 연결된 결과 ID. 업무키와 구분 |
| `Source_ID` | VARCHAR | sources.source_id를 참조하는 문서 ID |
| `주제` | VARCHAR | 문단의 검토 주제 |
| `탐색상태` | VARCHAR | 본문 후보 확보 상태 |
| `섹션명` | TEXT | 공시 절·제목 후보 |
| `일치키워드` | TEXT | 탐색에 일치한 키워드 |
| `원문발췌` | TEXT | 검토 문단의 원문 텍스트 |
| `시작문자` | INTEGER | 추출 텍스트 내 시작 위치(0 기반) |
| `끝문자` | INTEGER | 추출 텍스트 내 끝 위치(미포함) |
| `확인할질문` | TEXT | 감사인의 원문 확인 질문 |
| `연결기능` | TEXT | 후속 검토·분석 기능 |
| `원문링크` | TEXT | 공시 원문 URL |
| `검토상태` | VARCHAR | 사람의 검토 진행 상태 |

## 연결키와 집계

`review_passages.Source_ID → sources.source_id`의 N:1 관계입니다. 문서 한 건에서 주제별 문단 후보 여러 건을 관리합니다.

`Review_Record_ID`는 결과 행 식별자입니다. 표 간 연결에는 위 업무키·원본 행·자료 버전을 사용합니다.

## 이번 파일의 해석·확인 사항

`document_sha256`는 OpenDART에서 수신한 원문 ZIP 전체 바이트의 SHA-256입니다. `시작문자·끝문자`는 추출 텍스트의 0부터 시작하는 [시작, 끝) 위치입니다. 해시는 원본 식별용이며 변경 비교에는 이전 해시를 사용합니다. sources에는 사용자가 추가한 설명 행이 포함되어 있습니다.

## 파일 정보

제공된 입력·출력 사본을 보관했습니다. 설명·서식과 Excel 표시 변경이 포함될 수 있습니다. 재실행 시 슬롯별 파일·실행 조건·코드 버전을 함께 확인합니다. 데이터 사전의 타입은 DB 설계 제안입니다. [파일별 크기·SHA-256](../../artifact-manifest.json)
