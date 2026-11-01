# 로그 대사 기준과 처리 상태

GL과 로그의 금액 정의·통화·범위를 확인한 뒤 전표별 금액과 모집단을 비교합니다. 기준 정보가 부족하면 미실행 사유를 결과와 조서에 기록하고 GL 단독 검사를 이어갑니다.

## 결과 상태

| 상태 | 의미 |
|---|---|
| `basis_information_missing` | 금액·통화·범위의 근거 또는 확인·검토 정보 미확보 |
| `basis_not_comparable` | 양쪽 금액 필드·통화 기준·범위 차이 |
| `basis_evidence_invalid` | 근거 파일·입력 변경 또는 유효하지 않은 참조 |
| `matched` | 기준 확인 후 해당 대사에서 금액·범위 일치 |
| `differences_found` | 기준 확인 후 대사 차이 발견 |

미실행 차이 건수는 `null`로 보관하며 관련 결과표·상태·사유를 함께 제공합니다.

## 기준 확인 모델

| 구성 | 기록 내용 |
|---|---|
| `LogBasisConfirmation` | 원본 금액 필드, 통화 기준, 회사·연도·원장·기간, 추출 설명 |
| 입력 연결 | 검토한 GL·로그의 컬럼·행 순서·값에 대한 지문 |
| 검토 정보 | 확인자·검토자·검토일, 통화 확인 방식 |
| `EvidenceFile` | 전용 근거 폴더의 상대 경로·SHA-256·설명 |

입력 지문·파일 해시·경로를 검증하고 변경된 자료는 재확인 대상으로 반환합니다. 근거의 내용은 검토자가 확인합니다.

## 통화 처리

- `row_currency`: 로그의 행별 통화 사용.
- `confirmed_single_currency`: 근거로 확인된 단일 통화 사용.
- 기존 통화와 확인 통화가 다르면 충돌 이슈 반환.

## 서비스·조서 연결

`execute_analysis`는 입력 읽기·검증·계산을 공통 결과로 반환합니다. 입력 오류는 구조화된 표, 내부 오류는 사용자용 시스템 이슈로 제공합니다. `execute_batch`는 독립 분석의 결과를 모읍니다.

| 실행 상태 | 의미 |
|---|---|
| `completed` | 분석 결과 반환 |
| `completed_with_limitations` | 제한·이슈를 포함한 결과 반환 |
| `not_executed_input_issue` | 입력 문제로 계산 미실행 |
| `not_executed_system_issue` | 내부 처리 문제로 계산 미실행 |

조서 앞부분에 계산·로그 대사의 미실행 사유를 표시하고 감사인의 검토 상태를 별도로 기록합니다. 기준 확인은 Python 모델, 작업 접근과 검토 기록은 웹 서비스에서 관리합니다.

[기준 확인 코드](../src/audit_data_lab/reconciliation_basis.py) · [JET](../src/audit_data_lab/jet.py) · [서비스](../src/audit_data_lab/review_service.py)
