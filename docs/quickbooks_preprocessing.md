# QuickBooks 보고서 평탄화

기존 `/Users/saebom/ADS/samples/quickbooksGLtoDatabase.py`는 수정하지 않았습니다. 신규 함수 `reshape_quickbooks_report`는 예제와 같은 13열 보고서를 거래 표로 펼칩니다. 원본의 첫 행 6~13열은 정확히 Type, Date, Num, Name, Memo, Split, Amount, Balance여야 합니다. 앞 5열은 계정 표제입니다. 첫 시트만 읽습니다. 제목 행·지역별 열명·다른 QuickBooks 내보내기는 현재 지원하지 않으며 형식 오류로 보고합니다.

웹에서 QuickBooks 보고서 전처리를 선택하고 quickbooks 슬롯에 Excel 또는 동일한 원본 구조의 CSV를 업로드합니다. 조건 date_format은 %Y-%m-%d(기본), %m/%d/%Y, %d/%m/%Y, %Y%m%d 중 하나입니다. Excel 날짜 셀과 명시한 문자열 형식을 처리합니다. 숫자 날짜 일련번호를 자동 추정하지 않습니다.

ZIP의 review/analysis/modified_gl.csv는 펼친 거래입니다. row_dispositions.csv는 모든 원본 행의 처리 구분, review_rows.csv와 module_issues.csv는 미분류·거부 행과 원인입니다. 첫 논리 원본 레코드는 1이며 헤더·표제·합계도 원본 추적에 남깁니다. 금액은 쉼표 천 단위·괄호 음수·소수 둘째 자리까지 명시적으로 해석합니다. 통화 기호를 제거하거나 통화를 추정하지 않습니다.

변환에 문제가 있으면 conversion_status=incomplete_review_required로 표시하며, modified_gl은 부분 결과일 수 있습니다. CSV에도 Conversion_Status와 ADS_Status를 표시합니다. 합계·기초잔액 행은 거래로 중복 집계하지 않지만 해당 금액의 산술 대사까지 수행한 것은 아닙니다. 파일명 대소문자는 새 엔진의 modified_gl.csv를 따릅니다.

**ADS GL 변환이 아닙니다.** Num을 유일 전표 키로 추정하지 않고 계정 코드·통화·입력일·입력 사용자·회계기간을 만들지 않습니다. 해당 정보와 원본 범위를 확인한 별도 ADS 매핑이 있어야 기존 JET 및 사용자별 분할 입력으로 사용할 수 있습니다. 이 기능을 SAP 변환과 자동 연결하지 않습니다.

학습 노트북: notebooks/reshape_quickbooks_report.ipynb. 합성 데이터로만 검증하며 실제 QuickBooks 원본 예제 파일은 현재 프로젝트에 없습니다. 웹 자료는 기존 사용자 격리·권한·TTL을 따르고 노트북 outputs는 로컬 학습용입니다.
