# Audit Platform

**회계·재무 데이터 기반 감사지원 플랫폼입니다.**

회사 이해부터 데이터 처리, 감사 데이터 분석과 검토 조서 생성까지 연결했습니다.

[**웹에서 사용하기 ↗**](https://audit-platform-ow3x.onrender.com/) · [Frontend](frontend/README.md) · [Backend](backend/README.md)

## 프로젝트 소개

회계 자료를 분석한 뒤 결과의 근거를 확인하고 검토 내용을 정리하는 과정을 하나의 작업 공간으로 구현했습니다. AICPA ADS의 데이터 구조와 공개 Python 예제를 학습하고, 분석 함수를 FastAPI 기반 웹 서비스에 연결했습니다.

사용자가 직접 파일과 분석 조건을 입력하고, 분석 결과에서 원본 행을 확인한 뒤 검토 기록과 조서를 내려받을 수 있습니다.

## 주요 기능

| 영역      | 기능                                                         |
| --------- | ------------------------------------------------------------ |
| 회사 이해 | OpenDART 공시 조회와 원문 확인 |
| 데이터 처리 | SAP·QuickBooks 전처리, 입력 사용자별 GL 분할, 데이터 클렌징 |
| 감사 데이터 분석 | 총계정원장 테스트, 분석적 검토, 자금 대사, 재고 분석, 조회 회신 비교 |
| 결과 검토 | 원본 행 추적, 자료 버전 관리, 검토 기록, 조서 다운로드       |

## 대표 구현

### SAP 자료를 분석 가능한 GL·TB로 변환

BSEG 전표 상세와 BKPF 전표 헤더를 연결해 총계정원장을 생성하고, GLT0 잔액 자료를 시산표로 변환합니다. 전표의 차대 일치와 계정·기간별 GL–TB 움직임을 함께 확인합니다.

[변환 코드](src/audit_data_lab/sap.py) · [검증 코드](tests/test_sap_web.py)

### 중복 대사 후보를 검토 대상으로 분리

계좌·통화·금액·일자를 기준으로 은행과 장부의 거래를 비교합니다. 양쪽에서 후보가 하나인 경우에만 자동 연결하고, 같은 금액의 후보가 여러 개면 검토 대상으로 남깁니다.

[자금 대사 코드](src/audit_data_lab/cash.py) · [검증 코드](tests/test_deeper_analytics.py)

### 분석 결과에서 원본과 검토 기록까지 연결

결과 행에서 입력 자료의 원본 행과 적용 조건을 확인할 수 있습니다. 검토 메모와 참조를 기록하고, 분석 조서와 최신 검토 이력을 각각 다운로드할 수 있습니다.

[원본 추적 코드](src/audit_data_lab/traceability.py) · [검토 화면 설계](docs/review_workspace.md)

## 사용 방법

**기능 선택 → 분석 조건 설정 → 자료 업로드 → 분석 실행 → 결과 검토 → 조서 다운로드**

배포 사이트에서 **데모 시작**을 누르면 방문자 전용 작업 공간에 연결됩니다. KYC 공시 조회에는 본인이 발급받은 OpenDART 인증키를 입력합니다.

방문자별 작업은 분리되며, 작업 자료는 생성 후 기본 1시간에 만료됩니다. 필요한 결과는 다운로드해 보관합니다.

## 기술 구성

- **Frontend** — HTML, CSS, JavaScript
- **Backend** — Python, FastAPI, pandas, SQLite
- **배포·검증** — Docker, Render, GitHub Actions

로컬의 개발용 토큰 인증을 배포 환경의 방문자 쿠키 세션으로 확장했습니다. 파일 검증·작업 소유권 검사·만료 자료 정리를 적용하고, OpenDART 키는 해당 실행에서만 일시적으로 처리합니다.

[로컬 실행과 화면 구성](frontend/README.md) · [서버 구조와 키 처리](backend/README.md) · [배포 검증 기록](docs/deployment-verification.json)

## 학습과 개발

AICPA ADS 명세와 공개 Python 예제를 바탕으로 SAP·QuickBooks 자료 처리 흐름을 학습했습니다. 이를 토대로 입력 검증, 웹 분석 실행, 원본 추적, 검토 기록과 조회 회신 비교 기능을 구현·확장했습니다.

개발 과정에서 생성형 AI의 코드 작성·수정 지원을 활용했으며, 처리 조건과 결과를 테스트와 실행 사례로 확인했습니다.

[AICPA ADS 학습 정리](docs/portfolio/ads-learning.md) · [참고한 공개 Python 예제](https://github.com/AICPA-AuditDataAnalytics2018/ADS---Python-Example-)

## 향후 확장

- 업로드 미리보기와 컬럼 매핑 안내 개선
- Keycloak 기반 로그인과 역할별 검토·승인 흐름 추가
- 데이터베이스·파일 저장소·작업 큐 분리
- Git provider 연결을 통한 CI 통과 후 자동 배포 구성
