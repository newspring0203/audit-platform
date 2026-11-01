# Audit Platform

**회계·재무 데이터 분석부터 원본 확인, 검토 기록과 조서 다운로드까지 연결한 감사지원 플랫폼입니다.**

[웹에서 사용하기 ↗](https://audit-platform-ow3x.onrender.com/) · [시연 영상 ↗](https://www.youtube.com/watch?v=LWEW0ocwOVs) · [산출물 살펴보기](docs/portfolio/output-guide.md)

## 시연 영상

[▶ Audit Platform 시연 영상 보기](https://www.youtube.com/watch?v=LWEW0ocwOVs)

**원활한 시청을 위해 화질을 1080p로 설정해 주세요.**

자료 업로드 → 분석 실행 → 원본 확인 → 검토 기록 → 조서 다운로드를 시연합니다.

## 주요 기능

| 영역 | 기능 |
|---|---|
| 회사 이해 | OpenDART 공시 조회·주제별 검토 문단 추출 |
| 데이터 처리 | SAP·QuickBooks 전처리, 사용자별 GL 분할, 데이터 클렌징 |
| 감사 데이터 분석 | 총계정원장 테스트(JET), 분석적 검토, 조회 회신 비교, 자금 대사, 재고 분석 |
| 결과 검토 | 원본 행 추적, 자료 버전 비교, 증빙 참조·검토 기록, 조서 다운로드 |

## 대표 구현

### SAP 자료를 GL·TB로 변환하고 대사

BSEG 전표 상세와 BKPF 헤더를 연결해 GL을 생성하고, GLT0를 기간별 TB로 변환합니다. 키 중복·헤더 누락·결합 전후 행 수를 검사하고 전표 차대와 GL–TB 거래금액을 비교합니다.

[변환 코드](src/audit_data_lab/sap.py) · [필드 매핑과 검증](docs/sap_ads_mapping.md)

### 선정 이유와 예외를 함께 보여주는 분석

JET는 규칙별 선정 이유를 전표 단위 검토 목록으로 묶습니다. 자금 대사는 은행·장부 양쪽에서 유일한 후보만 연결하고, 중복 후보와 미대사는 후속 확인 대상으로 남깁니다. 입력 오류와 검사 미실행 사유도 결과에 기록합니다.

[JET 코드](src/audit_data_lab/jet.py) · [자금 대사 코드](src/audit_data_lab/cash.py) · [분석 기능 상세](docs/deeper_analytics.md)

### 결과에서 원본과 검토 기록까지 연결

결과 행에서 사용한 원본 자료와 계산 조건을 확인하고, 증빙 참조·검토 의견을 기록합니다. 분석 시점 조서와 이후 검토 이력을 각각 다운로드할 수 있습니다.

[원본 추적 코드](src/audit_data_lab/traceability.py) · [검토 공간 설계](docs/review_workspace.md)

## 산출물

기능별 입력·출력 파일과 시트 구조·주요 컬럼·실행 결과를 정리했습니다.

| 먼저 볼 산출물 | 확인할 내용 |
|---|---|
| [KYC 공시](docs/portfolio/artifacts/00-kyc/output-guide.md) | 공시 출처와 검토 문단 연결 |
| [QuickBooks 전처리](docs/portfolio/artifacts/02-quickbooks/output-guide.md) | 보고서에서 거래 표로 바뀌는 과정 |
| [총계정원장 테스트](docs/portfolio/artifacts/07-jet/output-guide.md) | 규칙별 선정 사유와 전표 검토 목록 |
| [분석적 검토](docs/portfolio/artifacts/08-analytical-review/output-guide.md) | 전기·당기 비교와 재무비율 |
| [자금 대사](docs/portfolio/artifacts/09-cash-proofing/output-guide.md) | 연결 후보·일치·미대사 구분 |

[전체 11개 기능의 산출물·파일 다운로드 →](docs/portfolio/output-guide.md)

## 기술 구성

| 구분 | 사용 기술 |
|---|---|
| Frontend | HTML · CSS · JavaScript |
| Backend·분석 | Python · FastAPI · pandas · SQLite |
| 배포·검증 | Docker · Render · GitHub Actions |

Python 분석 함수를 웹 서비스에 연결하고 작업별 자료 관리·파일 검증·사용자 소유권 확인·실행 시간 제한을 적용했습니다.

[Frontend 구성·실행](frontend/README.md) · [Backend 구조·실행](backend/README.md) · [배포·검증 기록](docs/deployment.md)

## 설계·학습 문서

| 주제 | 문서 |
|---|---|
| 기능·구조 | [기능별 구현](docs/platform_features.md) · [아키텍처](docs/architecture.md) |
| 감사 관점 | [기준과 구현 상태](docs/audit_standards.md) · [로그 대사 기준](docs/log_basis_policy.md) · [조회 회신 검토](docs/confirmation_review.md) |
| 데이터 처리 | [SAP 매핑](docs/sap_ads_mapping.md) · [QuickBooks](docs/quickbooks_preprocessing.md) · [사용자별 분할](docs/gl_user_split.md) |
| 검토·조서 | [검토 공간](docs/review_workspace.md) · [검토·조서 흐름](docs/page_review_flow.md) |
| 개발·학습 | [ADS 학습과 적용](docs/portfolio/ads-learning.md) · [Python 리팩터링](docs/python_backend_refactor.md) · [테스트 안내](tests/README.md) |

## 공식 참고문서

**AICPA의 Audit Data Standards(ADS) — General Ledger Standard를 데이터 구조 설계의 주요 참고 기준으로 활용했습니다.** GL·TB·계정과목표·전표 출처의 필드와 의미를 학습하고, 변환·검증 로직에 적용했습니다.

| 발행기관 | 공식 문서 | 프로젝트에서 참고한 내용 |
|---|---|---|
| **AICPA** | [**Audit Data Standards — General Ledger Standard (July 2015)**](https://www.aicpa-cima.com/resources/download/general-ledger-standard-audit-data-standards) | GL·TB·계정과목표·출처 목록의 데이터 구조와 필드 정의 |
| **PCAOB** | [**AS 1105 — Audit Evidence**](https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105) | 감사증거의 관련성·신뢰성, 회사 제공 정보의 정확성·완전성 평가 관점 |
| **AICPA** | [**Audit Evidence — SAS No. 142 At a Glance**](https://www.aicpa-cima.com/resources/article/audit-evidence) | 감사증거 평가에 관한 공식 개요 자료 |

[ADS 4개 데이터셋·69개 필드 학습 정리](docs/portfolio/ads-learning.md) · [기준별 적용 범위와 구현 상태](docs/audit_standards.md)

학습에는 [공개 Python 예제](https://github.com/AICPA-AuditDataAnalytics2018/ADS---Python-Example-)도 참고했으며, 입력 검증·웹 실행·원본 추적·검토 기록으로 확장했습니다. 개발 과정에서 생성형 AI의 코드 작성·수정 지원을 활용했습니다.
