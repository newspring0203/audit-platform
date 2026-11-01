# QuickBooks 보고서 평탄화

`reshape_quickbooks_report`는 계정 제목·거래·합계를 분리하고 거래마다 계정 정보를 붙입니다.

## 입력과 실행

| 항목 | 지원 형식 |
|---|---|
| 웹 입력 슬롯 | `quickbooks` |
| 파일 | XLSX 첫 시트 또는 같은 구조의 CSV |
| 열 구성 | 계정 표시 5열 + 거래 8열, 총 13열 |
| 거래 헤더 | Type, Date, Num, Name, Memo, Split, Amount, Balance |
| 문자열 날짜 | `%Y-%m-%d`, `%m/%d/%Y`, `%d/%m/%Y`, `%Y%m%d` |
| 금액 | 쉼표 천 단위·괄호 음수·소수 둘째 자리 |

Excel 날짜 셀과 지정 형식의 문자열을 해석합니다. 숫자 일련번호·통화 기호·다른 레이아웃은 형식 검토 대상으로 반환합니다.

## 출력

| 표 | 역할 |
|---|---|
| `modified_gl` | 계정명을 연결한 거래 |
| `row_dispositions` | 헤더·계정 제목·거래·합계 등 원본 행 분류 |
| `review_rows` | 미분류·거부 행 원본 |
| `module_issues` | 입력 오류와 확인 사항 |

`QuickBooks_Source_Row`는 거래 원본, `Account_Source_Row`는 계정 제목 원본 위치입니다. 합계·기초잔액은 거래와 분리해 처리 이력에 보존합니다.

## 함수 설계

계정 제목을 다음 거래행에 전달하고 모호한 경계에서는 연결을 해제합니다. 거래별 날짜·금액·계정·유형 검사를 통과한 행을 출력하며 거부 행은 별도 검토 목록에 남깁니다.

부분 변환은 `incomplete_review_required`, ADS 매핑 전 상태는 `not_converted`로 기록합니다. 후속 JET·사용자 분할에는 계정코드·통화·입력일·입력자·회계기간과 전표 식별자를 확인한 매핑 자료를 사용합니다.

[구현 코드](../src/audit_data_lab/quickbooks.py) · [테스트](../tests/test_quickbooks.py) · [산출물](portfolio/artifacts/02-quickbooks/output-guide.md)
