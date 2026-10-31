# Audit Platform · Backend

사용자가 업로드한 감사 자료를 작업별로 격리해 분석하고, 결과와 원본 연결 및 검토 조서를 제공하는 Python·FastAPI 서버입니다.

**[배포 사이트](https://audit-platform-ow3x.onrender.com/)** · [화면 이용법](../frontend/README.md) · [배포 상세](../docs/deployment.md)

## 기능과 실행 환경

SAP·QuickBooks 전처리, GL 분할, 데이터 클렌징, JET, 분석적 검토, 자금 대사, 재고 분석, 조회 회신 비교 및 OpenDART 공시 수집을 제공합니다. 공개 환경에서도 사용자 입력 조건과 업로드 파일을 그대로 검증·분석하며 고정된 예제를 강제로 주입하지 않습니다.

| 환경 | 인증 | 실행 |
|---|---|---|
| 로컬 `local` | 운영자 발급 개발용 Bearer 토큰 | `python scripts/run_local.py` |
| 공개 `demo` | 방문자별 HttpOnly·Secure·SameSite=Strict 쿠키 | `python scripts/run_server.py` |
| 비공개 `private` | 운영자 발급 Bearer 토큰 | `python scripts/run_server.py` |

공개 모드는 인증 방식의 차이이며 기능을 예제로 제한하는 모드가 아닙니다. 계정·SSO·역할별 기업 권한 관리는 별도 범위입니다. 현재 Render 무료 Docker 웹 서비스는 Singapore 지역 단일 인스턴스로 실행합니다. ASGI worker는 1개여야 하며 분석 자식 프로세스 수만 별도로 제한합니다.

## API 흐름

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 서버 상태 |
| GET | `/deployment-info` | 환경과 전체 기능 목록 |
| POST | `/demo/session` | 공개 방문자 세션 발급 |
| GET | `/api/features` | 기능·입력 자료·분석 조건 정의 |
| POST | `/api/jobs` | 사용자 조건으로 작업 생성 |
| PUT | `/api/jobs/{job_id}/inputs/{slot}` | 원본 바이트 업로드. `X-Filename` 필수 |
| POST | `/api/jobs/{job_id}/run` | 분석 실행. KYC는 별도 키 본문 사용 |
| GET | `/api/jobs/{job_id}` | 진행 상태·결과 식별자 |
| GET | `/api/jobs/{job_id}/review` | 결과와 검토 정보 |
| GET | `/api/jobs/{job_id}/downloads/{artifact_id}` | 인증·소유권 확인 후 ZIP 제공 |
| DELETE | `/api/jobs/{job_id}` | 작업 중지 및 자료 삭제 |
| POST | `/api/logout` | 세션 폐기 |

공개 환경의 상태 변경 요청에는 정확한 `Origin`과 `X-Audit-Request: 1`이 필요합니다. 인증 쿠키는 서버가 발급하고 토큰 값을 JSON으로 전달하지 않습니다. 다른 방문자의 작업·업로드·다운로드에는 접근할 수 없습니다.

일반 파일 분석은 작업 생성 → 자료 업로드 → 실행 순서입니다. 작업 생성 시 받은 `parameters`를 저장하며 API 키를 이 객체에 넣을 수 없습니다. 작업 상태 `completed`만으로 계산 성공을 판단하지 않고 결과의 `metadata.execution_status` 및 미실행 사유를 확인해야 합니다.

## 방문자 OpenDART 키 처리

KYC 작업의 실행 요청은 `POST /api/jobs/{job_id}/run`에 JSON 객체 `{ "dart_api_key": "본인이 발급받은 인증키" }`를 전달합니다. 실제 키를 예제 코드·명령줄·GitHub 이슈에 넣지 않습니다.

- 본인 작업 소유권을 먼저 확인하고, 요청 크기와 키 형식을 검사합니다.
- 공개 환경에서는 방문자 키를 명시적으로 요구합니다. 다른 방문자의 키나 운영자의 로컬 키로 대신 실행하지 않습니다.
- 키를 SQLite·작업 조건·spec.json·서버 파일·로그·결과 조서에 저장하지 않습니다.
- 분석 worker에는 명령줄 인자나 환경변수가 아닌 익명 표준입력 파이프로 전달합니다. 해당 작업에서만 메모리로 사용합니다.
- OpenDART의 고정 HTTPS API로만 전송하고 외부 리다이렉트를 따르지 않습니다. 키가 포함된 공급자 요청 URL과 상세 HTTP 예외를 로그·보고서에 남기지 않습니다.
- 브라우저 입력란은 실행 요청 시 비우며 브라우저 영구 저장소에 저장하지 않습니다. 입력 후 실행 전까지는 해당 화면 메모리에 존재합니다.

이는 서버가 키를 전혀 보지 않는 구조가 아닙니다. HTTPS 종단과 분석 프로세스가 요청·실행 중 키를 일시적으로 처리하며, Python 메모리의 물리적 완전 소거를 보증하지 않습니다. 서버가 중단되면 키를 복구하지 않으므로 새 작업에서 다시 입력해야 합니다. 로컬 환경은 별도 `.env` 방식도 유지합니다.

OpenDART의 키 유효성·요청 한도·네트워크 오류는 실제 조회 결과로 확인해야 합니다. 유효 키를 사용한 실제 공시 수집 성공을 모의 검증만으로 주장하지 않습니다. 선택적 AI 요약은 `AUDIT_ALLOW_AI=true` 및 서버의 OpenAI 설정이 별도로 필요하며 기본 비활성화입니다.

## 파일과 출력 정책

CSV·TXT·XLSX만 허용하며, 파일당 기본 20 MiB·작업 입력 합계 80 MiB를 제한합니다. XLSX 구조·압축 해제 용량·매크로·외부 링크·DTD/엔티티를 검사합니다. 원본과 결과는 웹 정적 경로가 아닌 전용 임시 저장소에 보관합니다.

기본 작업 TTL은 생성 후 3600초입니다. 만료 시 즉시 접근을 차단하고, 서버 실행 중 30초 간격 및 서버 시작 시 정리합니다. 방문자당 활성 작업은 기본 3개, 전체 20개이며 요청 수·동시 분석 수·실행 시간도 제한합니다. 무료 Render의 휴면·재시작·재배포 시 파일과 세션이 먼저 사라질 수 있습니다.

조서 ZIP은 CSV·JSON·Markdown과 검토 스냅샷을 포함합니다. XLSX 조서는 별도의 Node/Excel 렌더러를 설정한 환경에서만 생성되며 현재 기본 배포 이미지에는 포함하지 않습니다. 다운로드한 파일은 사용자 측에서 관리합니다.

## 로컬 실행과 배포

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-deploy.txt
.venv/bin/python scripts/run_local.py
```

배포는 `Dockerfile`과 `scripts/run_server.py`를 사용합니다. `PORT`를 받아 `0.0.0.0`에서 실행하며 `AUDIT_MODE=demo`, HTTPS `AUDIT_PUBLIC_ORIGIN` 또는 Render의 `RENDER_EXTERNAL_URL`, 전용 `AUDIT_RUNTIME_ROOT`가 필요합니다. 프로젝트 `.env`는 로컬에서만 읽고 저장소나 이미지에 포함하지 않습니다.

GitHub Actions는 공개 파일 검사·Python 테스트·JavaScript 세션 테스트·Docker 빌드를 실행합니다. Render의 정책 값은 `After CI Checks Pass`이지만, 현재 **공개 저장소 URL 직접 연결 방식에서는 자동 배포가 지원되지 않으므로 CI 성공 확인 후 수동 배포**합니다. 완전한 자동 배포에는 Git provider 연결이 필요합니다. [Render 공식 안내](https://render.com/docs/deploys#automatic-deploys)

## 검증

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend_session.test.mjs
.venv/bin/python scripts/check_publication.py
.venv/bin/python scripts/smoke_demo.py https://audit-platform-ow3x.onrender.com
```

공개 저장소에는 비공개 학습 노트북이 없으므로 노트북 대조 검사는 건너뜁니다. 합성 SAP 업로드·분석 검사는 별도로 실행합니다. 실제 서버 smoke 검사는 가상 예제 파일을 직접 업로드해 파일 분석 10종과 다른 방문자의 접근 차단, 키 입력 검증, 다운로드 ZIP 무결성을 확인합니다. 운영 데이터나 실제 인증키를 테스트 자료로 커밋하지 않습니다.
