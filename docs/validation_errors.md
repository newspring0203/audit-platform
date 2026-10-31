# 입력 오류 응답

검사: `src/audit_data_lab/validation.py`의 `validate_sap_inputs`.

오류가 있으면 `DataValidationError`가 발생합니다. `ValueError`를 상속하므로 기존 예외 처리와 호환됩니다. `.issues`는 오류 목록, `.to_frame()`은 노트북 표, `.to_dict()`는 JSON으로 전달 가능한 Python 사전입니다. API는 아직 구현하지 않았습니다.

각 항목은 `code`, `field`, `message`, `source_table`, `source_file`, `source_row`, `source_field`, `value`, `journal_id`, `severity`를 가집니다. 필드 누락처럼 특정 행에 속하지 않는 오류는 source_row=null입니다. field는 ADS 대상 필드이며, 누락 컬럼/범위 선택 키는 원본 필드명을 사용합니다. source_field는 SAP 컬럼명입니다.

행 번호는 정제·필터·결합 전 로딩 순서를 기준으로 헤더를 포함해 2부터 셉니다. TXT에 여러 줄 인용 필드가 있으면 논리적 표 행 번호와 실제 파일 줄 번호가 다를 수 있습니다. 현재 Excel은 첫 시트, 첫 행 헤더 기준입니다.

## 주요 코드

- MISSING_COLUMN / DUPLICATE_COLUMNS: 컬럼 누락·중복.
- MISSING_SCOPE_KEY / EMPTY_SCOPE: 범위 선택 키 누락·데이터 없음.
- MISSING_KEY / DUPLICATE_HEADER / DUPLICATE_DETAIL / HEADER_NOT_FOUND: 전표 연결 오류.
- INVALID_DATE / INVALID_TIME / INVALID_PERIOD: 날짜·시간·기간 오류.
- PERIOD_DATE_MISMATCH / FISCAL_YEAR_MISMATCH / SPECIAL_PERIOD_DATE_MISMATCH: 현재 달력연도 가정에 맞지 않음.
- INVALID_DC_CODE / MISSING_ACCOUNT: 차대변 코드·계정 오류.
- MISSING_AMOUNT / INVALID_AMOUNT / AMOUNT_PRECISION: 금액 오류.
- INVALID_CURRENCY / MULTIPLE_CURRENCIES: 통화 형식·기준 확인 필요.

독립적으로 검사 가능한 여러 오류를 함께 수집합니다. 필요한 컬럼이 없으면 후속 행 검사에 앞서 중단합니다. SAP 원본을 수정하거나 잘못된 값을 0으로 대체하지 않습니다.

노트북에서 오류를 저장하고 표로 표시한 뒤 중단합니다. 오류를 해결하고 해당 셀을 다시 실행하면 빈 오류 보고서로 갱신합니다. 정상 보고서의 input_validation_passed는 입력 검사 통과만 뜻하며 ADS 전체 준수 또는 변환 완료를 의미하지 않습니다. 예전 결과 CSV는 자동 삭제하지 않으므로 실패 시 새 결과로 사용하지 마세요.

파일 읽기 실패·환경 문제와 예상하지 못한 내부 예외는 이 입력 검사 모듈의 범위 밖입니다. API 구현 시 별도의 서버 오류 처리와 로그를 추가해야 합니다. 차대변 불균형·GL–TB 대사 차이는 기존 분석 결과 CSV로 계속 보고합니다.
