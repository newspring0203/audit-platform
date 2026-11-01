# 입력 검증과 오류 응답

`validate_sap_inputs`는 컬럼·범위·키·날짜·금액을 검사합니다. `DataValidationError`는 오류 목록을 표와 JSON으로 전달하며 웹 서비스가 후속 확인 사항을 연결합니다.

## 오류 구조

| 필드 | 의미 |
|---|---|
| `code`, `message` | 오류 유형·설명 |
| `field`, `source_field` | 검사 대상·원본 컬럼 |
| `source_table`, `source_file` | 원본 테이블·파일 |
| `source_row`, `value` | 원본 논리 행·문제 값 |
| `journal_id`, `severity` | 관련 전표·심각도 |

컬럼·범위 오류는 `source_row=null`로 기록합니다. 행 번호는 헤더 1행, 첫 논리 데이터 2행 기준입니다. XLSX는 첫 시트·첫 행 헤더, CSV의 여러 줄 셀은 논리 레코드 기준으로 추적합니다.

## 주요 코드

| 코드 | 검사 |
|---|---|
| MISSING_COLUMN / DUPLICATE_COLUMNS | 컬럼 누락·중복 |
| MISSING_SCOPE_KEY / EMPTY_SCOPE | 범위 선택 키·선택 데이터 |
| MISSING_KEY / DUPLICATE_HEADER / DUPLICATE_DETAIL / HEADER_NOT_FOUND | 전표 식별·헤더 연결 |
| INVALID_DATE / INVALID_TIME / INVALID_PERIOD | 날짜·시간·기간 |
| PERIOD_DATE_MISMATCH / FISCAL_YEAR_MISMATCH / SPECIAL_PERIOD_DATE_MISMATCH | 달력연도·기간·특별기간 조건 |
| INVALID_DC_CODE / MISSING_ACCOUNT | 차대변 코드·계정 |
| MISSING_AMOUNT / INVALID_AMOUNT / AMOUNT_PRECISION | 금액 결측·형식·정밀도 |
| INVALID_CURRENCY / MULTIPLE_CURRENCIES | 통화 형식·범위 |

## 처리 방식

독립 검사는 여러 오류를 수집하고 필수 컬럼 오류는 후속 행 검사 전에 반환합니다. 원본 값은 보존하며 입력 검사 결과와 전표 차대·GL–TB 대사 결과를 각각 제공합니다.

수정한 자료를 새로 검사하면 오류 보고서가 갱신됩니다. `input_validation_passed`는 입력 검사 상태이며 변환·대사 결과는 각 출력에서 확인합니다. 파일·시스템 오류는 `execute_analysis`가 공통 결과로 처리합니다.

[검증 코드](../src/audit_data_lab/validation.py) · [실행 서비스](../src/audit_data_lab/review_service.py)
