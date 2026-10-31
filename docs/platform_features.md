# 감사 지원 플랫폼 기능과 현재 범위

현재 FastAPI와 브라우저 JavaScript 화면에서 주요 Python 분석 함수를 실행합니다. SAP 전처리도 웹 메뉴에 연결했습니다. OpenDART·OpenAI는 키 설정과 서버 허용이 필요하며, 실제 실행 성공은 별도로 확인해야 합니다.

## 공통 흐름

원본 → 클렌징·ADS 변환 및 검증 → 분석 함수 → AnalysisResult(summary, tables, metadata) → CSV·JSON / 조서 초안 → API·웹 결과·검토 기록.

- `to_dict()`: 웹 API에서 사용할 JSON 호환 사전.
- `tables`: 노트북에서 확인할 DataFrame 목록.
- `save(directory)`: CSV와 요약 JSON 저장. 함수 자체는 원본을 수정하지 않음.
- `DataValidationError`: 오류 코드·필드·원본 표 행·설명. SAP 입력 검사에서 다수 오류를 모으며, 개별 분석 함수는 선행 조건 실패 시 중단할 수 있음.

## 기능별 구현 범위

| 기능 | Python 진입점 | 현재 범위 | 추가 개발 |
|---|---|---|---|
| 총계정원장 테스트 | jet.run_jet | 모집단·로그 총액 대사, 차대 불균형, 반복 계정금액, 정액, 주말·야간, 저빈도, 설정 기반 고액·결산 수동분개·문서일, 번호 공백 | 원전표-역분개 연결·사용자 이력 기반 위험 규칙 |
| 분석적 검토 | analytics.analytical_review | 2개 연도 계정별 순변동과 기간별 움직임, 증감률 | TB 잔액·계정과목표 기반 재무비율 및 차트 |
| 조서 | working_papers.generate_working_paper | 분석 조건·선정 이유·결과 파일을 포함한 Markdown/CSV 미검토 초안 | Excel·Word 서식, 증빙 링크·검토 이력 |
| KYC | kyc.kyc_review | OpenDART 수집·OpenAI 연결, 출처·근거 문구 검증 | 로컬 API 키 설정과 실시간 검증, 공시 유형 확대 |
| Cash Proofing | cash.cash_proofing | 계좌·통화·일자·부호 금액이 동일하고 양쪽 후보가 유일한 거래만 1:1 연결 | 시차·분할 거래·수수료·잔액조정·통제 검토 |
| 재고 | inventory.inventory_analysis | 기초+입고-출고 수량, 음수 재고·미출고 후보, 웹 차트용 결과 표 | 로트별 연령·재고금액·저가법·실사 대사·시각화 |
| 클렌징 | cleansing.profile_data / validation.validate_sap_inputs | 필드 프로파일·누락·형식·중복 보고; SAP 변환은 기존 노트북 | 다양한 입력 형식의 매핑과 웹 업로드 안내 |

일곱 범주의 기본 코드가 있다는 것이 일곱 완성 제품을 뜻하지는 않습니다. 기능 상태는 features.FEATURES에서도 제공합니다.

## JET 입력

- ADS GL: Journal_ID, GL_Account_Number, Business_Unit_Code, Fiscal_Year, Period, Amount, Amount_Currency, Amount_Credit_Debit_Indicator(D/C), Effective_Date, Entered_Date, Entered_By.
- Entered_Time: 선택(HHMM 또는 HHMMSS). Document_Date: 선택(보조 CSV).
- 표준화 로그: Journal_ID, Amount_Currency, Amount_Credit_Debit_Indicator(D/C), Total.
- 기존 예제 로그: `adapt_legacy_log`에 회사·연도·통화를 명시하여 변환. 원본 범위를 검증하지 않고 임의로 다른 회사 로그에 적용하지 않음.
- 고액 기준은 통화별로 설정. 결산 수동분개는 확인된 수동 출처와 결산일을 모두 설정한 경우만 적용. 미설정 규칙은 skipped_rules에 기록.
- 반복 계정금액은 같은 감사 단위·연도·기간·계정·통화·D/C·금액이 여러 고유 전표에 나타난 경우. 정상 정기 거래도 포함될 수 있음.
- 저빈도는 상세행 수가 아닌 고유 전표 수 기준. 번호 공백은 범위별 정렬·중복 제거 후 숫자 번호만 검사.
- 로그 금액은 전표·통화·D/C별 합산하며 음수 금액의 부호를 유지. 모집단 차이는 금액 0이어도 표시.

## Cash Proofing 입력

양쪽에 Row_ID, Bank_Account, Currency, Date(YYYYMMDD), Amount가 필요합니다. 입금/현금 증가 양수, 출금/현금 감소 음수로 통일해야 합니다. GL 전체가 아닌 식별한 현금·예금 거래와 은행 계좌 매핑을 준비해야 합니다. 반복 금액은 임의로 연결하지 않습니다.

## 재고 입력

수불: Item_ID, Date(YYYYMMDD), Quantity_In, Quantity_Out.
기초: Item_ID, Opening_Quantity(품목별 유일).
모든 품목에 명시적인 기초 수량이 필요합니다. 마지막 출고 후 경과일은 로트 재고 연령이 아닙니다. 출고 내역이 전혀 없는 재고는 경과일을 추정하지 않고 별도 표시합니다.

## 학습 순서

1. reshape_rename_sap_data.ipynb: SAP → GL/TB.
2. journal_entry_testing_final.ipynb: GL+로그 → jet.py → outputs/jet/<실행ID>.
3. platform_features_demo.ipynb: 나머지 기능을 작은 가상 데이터로 확인.
4. 브라우저에서 파일·조건을 지정해 공통 Python 분석 모듈 실행.

기존 ADS 예제를 참고해 분석 목적을 재구성했으며 기존 `/Users/saebom/ADS/` 파일은 수정하지 않았습니다.
