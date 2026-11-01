# 기능별 감사 목적과 현재 구현 범위

기준: 로컬 Python·API 구현. 화면 분석 메뉴 0~10번과 공통 조서 기능을 구분합니다. 메뉴 번호는 수행 순서가 아닙니다. 전체 개요와 핵심 코드 예시는 [루트 README](../README.md), 함수 등록은 [features.py](../src/audit_data_lab/features.py)를 참고합니다.

## 공통 계약

파일·조건 → 검증·변환 → 목적별 분석 → `AnalysisResult(summary, tables, metadata)` → 원본 연결·웹 검토·조서입니다. 원본을 임의로 수정하지 않고 새 결과를 반환합니다. 정리된 표의 의미·범위·통화가 맞는지 확인한 뒤 분석해야 합니다. QuickBooks 평탄화나 컬럼명 매핑만으로 ADS 전체 준수를 주장하지 않습니다.

| 기능 | 감사 목적 / 단위 | 핵심 함수 | 주요 결과 | 확인해야 할 한계 |
|---|---|---|---|---|
| 0 KYC | 기업 이해 / 공시·주제 문단 | `kyc_review`, `extract_review_passages` | sources, review_passages, 선택 insights·evidence | 주제당 최대 1건 후보. 미확보는 관련 사항 없음이 아님 |
| 1 SAP | 자료 표준화 / 전표 상세·기간 잔액 | `convert_sap_data` | gl, tb, nonbalancing_journals, gl_tb_reconciliation, sap_lineage | 달력연도·소수 2자리·단일 추출 범위 전제 |
| 2 QuickBooks | 보고서 평탄화 / 거래행 | `reshape_quickbooks_report` | modified_gl, row_dispositions, review_rows, module_issues | 지원 13열 레이아웃. ADS 변환은 별도 |
| 3 사용자 분할 | 검토 자료 배분 / GL 행 | `split_gl_by_user` | group_index, row_membership, user별 표 | 전표 전체를 한 그룹에 보장하지 않음 |
| 4 클렌징 | 품질 진단 / 컬럼·원본 행 | `cleanse_data`, `profile_data` | field_profile, issues, duplicate_rows, mapping_suggestions, mapped_data | 명시적 매핑으로 이름만 변경. 자동 삭제·0 보정 없음 |
| 5 AR 회신 | 장부·외부 회신 비교 / 조회 항목 | `ar_confirmation_review` | confirmation_comparison, review_items, unlinked_replies | 발송·회수 통제·진위·대체절차 별도 |
| 6 은행 회신 | 잔액·계약조건 비교 / 계좌·항목 | `bank_confirmation_review` | AR 공통 결과 + terms_review | 문자열 일치는 원문 검토 완료가 아님 |
| 7 JET | 전표 후보 선정 / 분개×규칙·전표 | `run_jet` | flagged_lines, journal_review_queue, 로그 대사·번호 공백·기준 이슈 | 규칙 수는 위험 확률 아님. 로그 대사는 근거 게이트 필요 |
| 8 분석적 검토 | 변동 파악 / 계정·기간·통화 | `analytical_review`, `review_tb` | 월별·연도별 GL, TB 비교, 비율·구성금액·기간 범위 | TB 기간은 GL 필터 아님. 비율은 분류·부호 기준 필요 |
| 9 자금 대사 | 은행·장부 연결 / 거래 쌍 | `cash_proofing` | candidate_links, matches, unmatched, review_items, balance_reconciliation | 상호 유일 1:1. 시차 허용 가능, 분할 결제 자동 추정 없음 |
| 10 재고 | 수량 흐름 / 품목·수불·로트 | `inventory_analysis` | item_summary, timeline, negative_events, 월별·로트·수량 대사 | 미출고 일수는 로트 연령 아님. 실사·평가 별도 |
| 공통 조서 | 결과 문서화 / 분석 실행 | `generate_working_paper`, `write_job_report` | Markdown·CSV·JSON·ZIP, 설정 시 Excel | 미검토 초안. 승인·서명 자동 생성 없음 |

빈 표는 입력 범위에 후보가 없거나 해당 부가 분석을 수행하지 못한 경우 모두 발생할 수 있습니다. 요약·metadata·issues를 함께 확인합니다. 내부 반환표와 내보낸 파일의 구성이 같다고 가정하지 않습니다.

## 입력과 연결 단위

- SAP: 회사·연도·전표번호로 BSEG→BKPF many-to-one. GLT0는 회사·연도·원장·실적구분·버전 선택 후 집계. 현 결합키에는 MANDT 미포함.
- KYC: `review_passages.Source_ID → sources.source_id`의 N:1. 해시는 원문 ZIP 전체 바이트이며 추출 텍스트 해시가 아님.
- 조회: 장부·요청은 사업단위·대상·통화·기준일, 요청·회신은 Request_ID 연결 후 범위 재확인. 금액 차이는 장부−회신.
- JET: 전표·통화·D/C별 로그 합계. 사용자·계정 빈도는 상세행 수가 아닌 고유 전표 수.
- 분석적 검토: 사업단위·계정·통화를 분리한 GL 순변동. TB는 연도·선택 기간별 잔액이며 계정 분류는 사업단위+계정으로 연결.
- 자금: bank/cash_gl의 Row_ID는 각 자료 내부 키. 계좌·통화·부호 금액·허용 날짜로 후보 생성 후 상호 유일성 확인.
- 재고: Item_ID로 기초와 수불 집계 연결. 품목·로트 키 검증 후 로트 합계와 수불 기말 대사. 모든 수불 품목에 명시적 기초 필요.

## 실행·예외 처리

`execute_analysis`는 예상 입력 오류를 `not_executed_input_issue`, 내부 예외를 `not_executed_system_issue`로 반환합니다. 내부 경로·인증정보는 사용자 오류에 노출하지 않습니다. 선택적 TB·잔액·로트 검사 실패는 가능한 독립 분석과 함께 이슈로 남깁니다. 개별 상태·생략 규칙도 함께 확인해야 하며 전체 completed가 감사 완료를 뜻하지 않습니다.

`Review_Record_ID`는 실행·표·행 위치 기반 결과 ID입니다. 업무키·원본 행·자료 버전과 구분합니다. 여러 파일을 통합할 때는 Source_File_ID 같은 출처 식별자와 업무키를 함께 설계해야 합니다.

## 검증·후속 개발

합성 입력 테스트와 실제 외부 API 실행 검증을 구분합니다. 관련 검사는 `tests/test_sap_to_ads.py`, `test_quickbooks.py`, `test_gl_user_split.py`, `test_confirmations.py`, `test_log_basis.py`, `test_deeper_analytics.py`, `test_review_workspace.py`에서 확인할 수 있습니다. 현재 변경에서의 실행 여부는 별도 기록해야 하며 고정 테스트 수를 최신 성공 건수로 재사용하지 않습니다.

추가 과제는 실제 ERP 레이아웃·회계달력·통화 정밀도, 분할 거래, 역분개 연결, 재고 평가·실사 연결, 팀 역할·승인과 운영 보관 체계입니다. 원장·공시 분석이 전체 감사 절차나 증거 충분성을 대신하지 않습니다.
