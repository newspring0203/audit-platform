# 공식 참고 기준과 구현 적용

**AICPA ADS의 데이터 구조와 공식 감사증거 자료를 참고해, 회계자료 변환·검증·원본 추적 기능을 설계했습니다.**

## 참고한 공식 문서

| 발행기관 | 문서 | 프로젝트 적용 |
|---|---|---|
| **AICPA** | [**ADS — General Ledger Standard (July 2015)**](https://www.aicpa-cima.com/resources/download/general-ledger-standard-audit-data-standards) | GL·TB·계정과목표·출처 목록의 필드 정의와 데이터 구조 |
| **PCAOB** | [**AS 1105 — Audit Evidence**](https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105) | 회사 제공 정보의 정확성·완전성, 감사증거의 관련성·신뢰성 평가 관점 |
| **AICPA** | [**Audit Evidence — SAS No. 142 At a Glance**](https://www.aicpa-cima.com/resources/article/audit-evidence) | 감사증거 평가에 관한 공식 개요 |

[ADS 4개 데이터셋·69개 필드 학습 정리](portfolio/ads-learning.md)

## 설계에 적용한 내용

| 설계 항목 | 적용 내용 | 구현 |
|---|---|---|
| 데이터 구조 | SAP 필드를 GL·TB의 컬럼과 코드로 변환 | [sap.py](../src/audit_data_lab/sap.py) |
| 변환 검증 | 키 중복·헤더 미연결·행 수·금액 보존 검사 | [validation.py](../src/audit_data_lab/validation.py), [sap.py](../src/audit_data_lab/sap.py) |
| 대사 기준 확인 | 금액 필드·통화·회사·기간·추출 범위와 검토 근거 확인 | [reconciliation_basis.py](../src/audit_data_lab/reconciliation_basis.py) |
| 수행 상태 구분 | 기준 미확보·대사 일치·차이 발생을 별도 상태로 기록 | [jet.py](../src/audit_data_lab/jet.py) |
| 원본 추적 | 자료 버전·해시·원본 행·계산 조건을 결과와 연결 | [traceability.py](../src/audit_data_lab/traceability.py) |
| 검토 기록 | 선정 이유·증빙 참조·검토 의견·상태와 이력 보관 | [review_routes.py](../backend/app/review_routes.py) |

## 로그 대사 기준 확인

| 단계 | 확인·처리 내용 |
|---|---|
| 1. 범위 확인 | 회사·원장·기간·추출 조건과 금액·통화·부호·집계 단위 확인 |
| 2. 근거 연결 | 추출 명세·필드 설명·근거 파일과 확인자·검토자·검토일 기록 |
| 3. 입력 검증 | 검토한 GL·로그의 지문과 근거 파일 해시 대조 |
| 4. 대사 실행 | 확인된 기준으로 전표·통화·차대변별 금액과 모집단 비교 |
| 5. 결과 기록 | 일치·차이 또는 미실행 사유를 결과와 조서에 기록 |

기준 정보가 부족하면 `basis_information_missing`으로 기록하고, 가능한 GL 단독 검사는 별도로 수행합니다. 미실행 검사의 차이 건수는 `null`로 보관합니다.

[로그 대사 정책](log_basis_policy.md) · [SAP 필드 매핑](sap_ads_mapping.md) · [원본 추적·검토 공간](review_workspace.md)

## 적용 범위와 확장

현재 구현은 SAP 예제 변환·입력 검증·로그 기준 확인·원본 연결·검토 기록을 지원합니다. 실제 자료 적용 시 통화·사업단위·역분개·출처 코드의 의미를 확인하며, 후속 개발은 역할별 승인과 장기 보관 체계를 중심으로 확장합니다.
