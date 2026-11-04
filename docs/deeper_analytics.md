# 분석 기능 확장

개발용 Python 엔진과 웹 API에 다음 기능을 연결했습니다. 검토 후보·선정 사유·검사 수행 상태를 제공합니다.

| 기능 | 추가 결과 | 추가 입력 / 제한 |
|---|---|---|
| JET | 여러 규칙이 동시에 걸린 전표 검토 목록, 차변·대변 별도 합계 | combined_rule_min 기본 2. 규칙 개수는 위험 확률이 아님 |
| 분석적 검토 | 월별 전년 비교, 기간 범위 차이, TB 잔액 비교, 유동비율·운전자본·부채자본비율 | TB 및 계정 분류, 선택 기간, debit_positive 부호 기준 필요. 누락 잔액 별도 표시 |
| Cash | 허용 시차 후보, 유일한 상호 1:1 연결, 중복 후보, 미대사 경과일, 잔액 조정 산식 | 통화·계좌·부호 일치 필수. 조정 근거 누락 별도 표시 |
| 재고 | 일자 순 누적 수량·중간 음수, 월별 수불, 기말 로트 연령 구간 | 로트 잔여수량과 기말 수량이 대사된 품목만 연령 집계. 같은 날 실제 거래 순서는 알 수 없음 |
| 클렌징 | 컬럼 매핑 제안·모호성·충돌 확인, 명시적 매핑 적용 | 이름 변경만 수행. S/H 값·통화 의미·복합키 생성은 별도 변환 필요 |
| KYC | 사업·반기·분기 보고서 선택, AI 실패 시 공시 근거 보존 | 실제 키 실행 미검증. 외부 제공 범위와 설정은 기존 보안 정책 적용 |
| 조서 | 추가 분석 표 CSV, 모듈 오류 목록과 미실행 이유, 비 JET 요약 교정 | 기능별 전용 Excel 레이아웃과 차트는 후속 작업 |

## 웹 API에서 선택 가능한 추가 입력

`GET /api/features`의 required_inputs / optional_inputs를 사용합니다. 기존 inputs는 업로드 허용 슬롯 전체입니다.

- analytical_review: 선택 tb, account_mapping. 조건 tb_period, tb_sign_basis.
- cash_proofing: 선택 balances. 조건 date_tolerance_days, as_of, aging_days.
- inventory: 선택 lot_snapshot. 조건 as_of, stale_days.
- data_cleansing: 선택 mapping.
- kyc: 조건 report_type = A001 / A002 / A003.

## 추가 입력 형식

계정 분류: Business_Unit_Code, GL_Account_Number, Metric_Group, Sign_Multiplier.
Metric_Group은 current_assets / noncurrent_assets / current_liabilities / noncurrent_liabilities / equity / other. 배수는 1 또는 -1로 명시합니다. BU·통화·연도별로 분리 계산합니다.

TB: Business_Unit_Code, GL_Account_Number, Fiscal_Year, Period, Amount_Currency, Amount_Ending. 실제 필드 검증은 financial_review.py 참고.

잔액 확인: Bank_Account, Currency, As_Of_Date, Bank_Balance, GL_Balance, Bank_Adjustment, Adjustment_Reference. Bank_Balance + Bank_Adjustment와 GL_Balance의 산식 비교입니다. 근거 자료는 검토 기록에 연결합니다.

로트: Item_ID, Lot_ID, Receipt_Date, Snapshot_Date, Remaining_Quantity.
매핑: Target_Field, Source_Field.

## 설정·계산 단위

- JET의 화면 라벨은 저빈도 최대 행 수지만 실제 `nunique(Journal_ID)` 기준입니다. 중복 규칙을 제거한 전표별 규칙 수로 검토 목록을 정렬합니다.
- 분석적 검토의 `tb_period='10'`은 TB 잔액 비교에 적용하는 회계기간입니다. `tb_sign_basis='debit_positive'`는 차변 양수·대변 음수의 원본 부호 기준 확인입니다. GL 순변동과 시점 TB 잔액을 구분합니다.
- 자금 대사의 연결 조건은 동일 계좌·통화·부호 금액 및 설정 시차이며 양쪽에서 유일한 후보를 연결합니다. 잔액식은 은행+조정−장부입니다.
- 재고는 모든 수불 품목의 명시적 기초가 필요하고 기말 음수와 중간 음수를 별도로 계산합니다. 같은 날의 수불은 원본 행 순서로 계산합니다.
- 조회 회신 차이는 장부−회신이며 같은 기준일의 confirmed 회신만 비교합니다. 허용차이 이내라도 비영 차이는 검토 대상으로 남깁니다.

자세한 함수와 오류 처리는 [README](../README.md#주요-기능), [로그 정책](log_basis_policy.md), [조회 회신](confirmation_review.md)을 참고 부탁드립니다.
