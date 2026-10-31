# Audit Platform — Backend

회계감사 데이터 분석을 위한 **Python·FastAPI 기반 백엔드 서버**입니다.

사용자가 업로드한 회계 데이터를 작업별로 관리하고, Python 분석 엔진을 실행한 뒤 분석 결과와 원본 근거를 조회할 수 있도록 구현하였습니다.

**자료의 소유권 관리, 분석 실행 이력, 원본 추적, 검토 기록 및 감사조서 출력**을 지원합니다.

## 1. 주요 기능

| 기능           | 설명                                               |
| -------------- | -------------------------------------------------- |
| 작업 관리      | 사용자별 분석 작업 생성, 상태 조회 및 만료 처리    |
| 자료 업로드    | GL·TB 등 분석 입력 자료의 업로드 및 검증           |
| 분석 실행      | Python 분석 엔진 호출 및 작업 실행 상태 관리       |
| 결과 조회      | 분석 결과, 계산 조건, 원본 행 및 검토 대상 조회    |
| 원본 추적      | 업로드 자료와 분석 결과 간의 연결 정보 관리        |
| 검토 기록      | 검토 의견, 기준서 참조 및 검토 이력 보관           |
| 감사조서 생성  | 분석 결과를 CSV·JSON·Markdown·ZIP으로 제공         |
| 접근 제어      | Bearer 토큰 인증 및 회사·사용자·작업별 소유권 검사 |
| 임시 자료 관리 | 작업 만료, 파일 삭제 및 정리 작업 수행             |

Excel 렌더러가 서버에 설정되어 Excel 출력을 지원합니다.

## 2. 시스템 구조

### 2.1 전체 처리 흐름

**Frontend → FastAPI → 작업·권한 검증 → Python 분석 엔진 → 결과 저장 → 원본 추적 및 검토 → 감사조서 출력**

프론트엔드, API 서버, 분석 엔진의 역할을 분리하여 구성하였습니다.

| 구성 요소              | 역할                                                  |
| ---------------------- | ----------------------------------------------------- |
| Frontend               | 분석 조건 입력, 자료 업로드, 결과 및 원본 조회        |
| FastAPI Backend        | 인증, 작업 관리, 입력 검증, 분석 실행 및 결과 제공    |
| Python Analysis Engine | SAP 전처리, JET, 분석적 검토, 자금 대사, 재고 분석 등 |
| Reporting              | 분석 결과와 검토 정보를 파일로 출력                   |

### 2.2 주요 코드 구조

| 파일                       | 역할                             |
| -------------------------- | -------------------------------- |
| `app/main.py`              | FastAPI 애플리케이션 생성        |
| `app/job_routes.py`        | 분석 작업 생성·조회·실행 API     |
| `app/uploads.py`           | 자료 업로드 및 입력 처리         |
| `app/worker.py`            | 분석 작업 실행 관리              |
| `app/analysis_dispatch.py` | 기능별 Python 분석 함수 호출     |
| `app/reporting.py`         | 분석 결과 및 감사조서 출력       |
| `app/manage.py`            | 개발 토큰 발급 및 임시 자료 정리 |

실제 분석 함수는 `src/audit_data_lab/`에 별도로 구성되어 있습니다.

백엔드는 사용자의 요청과 Python 분석 엔진을 연결하며, 인증과 작업 상태, 결과 제공을 담당합니다.

## 3. API 설계

모든 `/api` 경로에는 Bearer 토큰 인증이 필요합니다.

### 3.1 주요 API

| Method | Endpoint                                     | 기능                        |
| ------ | -------------------------------------------- | --------------------------- |
| GET    | `/api/features`                              | 분석 기능 및 입력 조건 조회 |
| POST   | `/api/jobs`                                  | 분석 작업 생성              |
| PUT    | `/api/jobs/{job_id}/inputs/{input_name}`     | 분석 자료 업로드            |
| POST   | `/api/jobs/{job_id}/run`                     | 분석 실행                   |
| GET    | `/api/jobs/{job_id}`                         | 작업 상태 및 결과 정보 조회 |
| GET    | `/api/jobs/{job_id}/downloads/{artifact_id}` | 결과 ZIP 다운로드           |
| DELETE | `/api/jobs/{job_id}`                         | 작업 중지 및 자료 삭제      |
| POST   | `/api/logout`                                | 접근 토큰 폐기              |

### 3.2 분석 실행 예시 — JET

**① 분석 작업 생성**

`POST /api/jobs`

요청 본문 예시:

`{"module":"jet","parameters":{"company":"3000","fiscal_year":"2007"}}`

**② 분석 입력 자료 업로드**

`PUT /api/jobs/{job_id}/inputs/gl`

`PUT /api/jobs/{job_id}/inputs/log`

원본 파일 바이트와 `X-Filename` 헤더를 전달합니다.

**③ 분석 실행 및 상태 확인**

`POST /api/jobs/{job_id}/run`

`GET /api/jobs/{job_id}`

**④ 결과 다운로드**

`GET /api/jobs/{job_id}/downloads/{artifact_id}`

다운로드 요청 시에도 인증, 작업 소유권 및 만료 여부를 확인합니다.

**작업 상태 `completed`는 계산 처리가 종료되었다는 의미입니다.**

입력 부족 등으로 검사를 수행하지 못한 경우에는 미실행 사유와 후속 확인 사항을 결과에 기록합니다.

## 4. 회계 데이터 보호 및 접근 제어

회계 데이터의 기밀성과 분석 결과의 추적 가능성을 고려하여 접근 제어, 파일 검증, 임시 저장 정책을 구현하였습니다.

### 4.1 접근 제어

- 회사·사용자·작업별로 자료와 결과를 분리합니다.
- 토큰에서 확인한 회사·사용자 정보를 기준으로 작업 소유권을 검증합니다.
- 동일 회사의 다른 사용자도 기본적으로 타인의 작업에 접근할 수 없습니다.
- 요청 본문이나 `X-User-ID`를 통한 소유자 변경을 허용하지 않습니다.
- 토큰 원문 대신 해시를 서버에 저장하고, 만료 및 로그아웃 시 폐기합니다.

### 4.2 파일 업로드 및 저장 정책

| 항목             | 개발 환경 기본 정책               |
| ---------------- | --------------------------------- |
| 단일 업로드 파일 | 최대 20MB                         |
| 작업당 전체 입력 | 최대 80MB                         |
| 압축 해제 크기   | 최대 128MB                        |
| 데이터 크기      | 최대 100,000행·256열              |
| 텍스트 인코딩    | UTF-8·CP949                       |
| 디렉터리 권한    | `0700`                            |
| 파일 권한        | `0600`                            |
| 저장 파일명      | 원본 파일명 대신 UUID 사용        |
| 파일 검사        | 매크로·암호화 XLSX·외부 링크 거절 |

작업별 비공개 폴더를 사용하며, 업로드 파일을 정적 웹 경로로 직접 노출하지 않습니다.

### 4.3 작업 및 자원 관리

| 항목                  | 개발 환경 기본값 |
| --------------------- | ---------------- |
| 사용자당 유효 작업    | 최대 3개         |
| 전체 작업             | 최대 50개        |
| 동시 실행             | 최대 2개         |
| 분석 실행 제한        | 120초            |
| 작업 만료             | 생성 후 1시간    |
| 자동 정리 주기        | 30초             |
| 최소 보안 이벤트 보관 | 기본 24시간      |

작업 만료 시 접근을 거절하고 실행 프로세스 및 관련 임시 파일을 정리합니다.

작업 자료, 보고서, 미리보기 및 검토 이력은 작업별 저장 범위에서 함께 관리합니다.

## 5. 분석 결과 및 감사 추적성

분석 결과를 **어떤 입력 자료와 계산 조건으로 결과가 생성되었는지 확인할 수 있도록** 구성하였습니다.

**입력 자료 → 실행 조건 → Python 계산 → 분석 결과 → 원본 연결 → 검토 기록 → 감사조서**

주요 관리 정보는 다음과 같습니다.

- 업로드 원본의 SHA-256 해시와 자료 버전
- 분석 실행 조건 및 코드 해시
- 분석 결과와 연결된 원본 행 또는 집계 입력 범위
- 검토 의견, 증빙 참조 및 변경 이력
- 분석 실행 시점의 결과와 후속 검토 기록

감사조서는 분석 실행 시점의 결과를 제공하며, 이후 수정된 최신 검토 이력은 별도로 관리합니다.

원본 추적은 업로드된 자료부터 시작하며, ERP 최초 추출 과정 전체의 완전성을 입증하지 않습니다.

상세한 추적 방식과 구현 범위는 [감사 분석 결과의 출처 추적 및 검토 관리 설계](../docs/review_workspace.md)를 참고하세요.

## 6. 로컬 실행 및 검증

프로젝트 루트에서 개발용 접근 토큰을 발급한 뒤 FastAPI 서버를 실행합니다.

**토큰 발급**

`.venv/bin/python -m backend.app.manage --root .runtime issue-token --tenant demo-company --user reviewer --token-file .runtime/reviewer.token`

**서버 실행**

`.venv/bin/python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log`

서버 시작 후 `http://127.0.0.1:8000/`에서 웹 화면을 사용할 수 있습니다.

자세한 실행 환경과 전체 검증 방법은 프로젝트 루트 README 및 관련 문서를 참고하세요.

## 7. 현재 구현 범위와 한계

현재 백엔드는 **단일 호스트·단일 ASGI 프로세스 기반의 MVP**입니다.

다음 항목은 공개 배포 또는 실제 운영 환경 적용 전에 별도 검토가 필요합니다.

- 운영용 인증 및 계정 관리(SSO/OIDC 등)
- 조직 단위 권한 관리
- HTTPS·TLS 및 리버스 프록시 구성
- 저장소 암호화와 키 관리
- 컨테이너 및 분석 프로세스의 자원 격리
- 장애 발생 시 외부 정리 작업 및 모니터링
- 백업, 자료 보존 및 삭제 정책

API 및 다운로드 응답에 `Cache-Control: private, no-store`를 적용하지만 이미 다운로드된 파일의 회수를 보장하지는 않습니다.

OS 파일 삭제는 SSD 또는 백업 매체에서의 완전한 보안 소거를 보장하지 않습니다.

AI 기능은 서버에서 기본 비활성화되어 있으며, 실제 외부 AI 호출 성공 여부는 별도의 검증 과제입니다.

## 8. 상세 문서 및 참고 자료

### 프로젝트 문서

- [감사 분석 결과의 출처 추적 및 검토 관리 설계](../docs/review_workspace.md)
- [백엔드 보안 검증 기록](../docs/backend_security_verification.md)
- [캐시 및 데이터 보존 정책](../docs/cache_and_retention.md)
- [전체 프로젝트 소개](../README.md)

### 공식 기술 참고 자료

- [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [MDN Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
