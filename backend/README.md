# Audit Platform · Backend

**사용자가 올린 회계 자료를 작업별로 관리하고, Python 분석 엔진을 실행해 검토 조서를 제공하는 서버입니다.**

Python · FastAPI · SQLite · Docker로 구성했습니다.

[**배포 사이트 ↗**](https://audit-platform-ow3x.onrender.com/) · [Frontend](../frontend/README.md) · [API 상세](../docs/backend-api.md) · [배포 설정](../docs/deployment.md)

## 처리 흐름

**요청 인증 → 작업 생성 → 파일 검증 → 분석 프로세스 실행 → 결과·원본 연결 → 조서 다운로드**

SAP·QuickBooks 전처리, GL 분할, 데이터 클렌징, JET, 분석적 검토, 자금 대사, 재고 분석, 조회 회신 비교, OpenDART 공시 수집을 담당합니다.

## 로컬에서 배포까지

| 구분 | 로컬 | Render 배포 |
|---|---|---|
| 서버 | loopback 주소에서 실행 | Docker·플랫폼 포트·HTTPS |
| 인증 | 개발용 Bearer 토큰 | 방문자별 보안 쿠키 |
| 저장 | SQLite·로컬 작업 폴더 | SQLite·서버 임시 작업 폴더 |
| OpenDART 키 | 로컬 설정 또는 실행 시 입력 | 방문자가 실행할 때 입력 |

**로컬 구현**에서는 작업 소유권 검사, 업로드 검증, 분석 프로세스 분리, 실행 시간 제한과 만료 자료 정리를 구성했습니다.

**배포 과정**에서는 환경변수 기반 실행 설정, 방문자 쿠키 인증, 동일 원점 검사와 일회성 OpenDART 키 전달을 추가했습니다. 사용자 파일과 분석 조건은 로컬과 동일한 흐름으로 처리합니다.

## 인증과 자료 관리

- **작업 격리** — 모든 자료·결과 요청에서 방문자와 작업 소유권 확인
- **요청 보호** — HttpOnly·Secure·SameSite 쿠키, 상태 변경 요청의 Origin 검사
- **파일 검증** — CSV·TXT·XLSX 형식·용량 검사, XLSX 매크로·외부 연결·압축 구조 검사
- **자원 제한** — 방문자당 활성 작업 3개, 전체 20개, 분석 시간·동시 실행 수 제한
- **자동 정리** — 작업 생성 후 기본 1시간에 접근 만료, 서버 실행 중 30초 간격으로 삭제

파일당 기본 한도는 **20 MiB**, 작업 입력 합계는 **80 MiB**입니다. 원본과 결과는 전용 임시 폴더에 저장하며, 무료 서버의 휴면·재시작·재배포 시 먼저 사라질 수 있습니다.

### 방문자 OpenDART 키

키는 일반 분석 조건과 분리해 해당 작업 실행 시에만 전달합니다. 분석 프로세스에는 익명 파이프로 전달하고, 서버 파일·로그·조서에는 저장하지 않습니다. 브라우저 입력란도 요청 시 비웁니다.

키는 HTTPS 요청과 분석 중 메모리에서 일시적으로 처리합니다. 처리 경로와 검증 범위는 [키 처리 상세](../docs/backend-api.md#방문자-opendart-키-처리)에 정리했습니다. AI 요약은 별도 OpenAI 설정으로 활성화하는 선택 기능입니다.

## 실행과 배포

저장소 루트에서 로컬 서버를 실행합니다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-deploy.txt
.venv/bin/python scripts/run_local.py
```

배포 서버는 `Dockerfile`과 `scripts/run_server.py`를 사용합니다. `PORT`, `AUDIT_MODE`, HTTPS 원점, 임시 저장 경로를 환경변수로 설정합니다. 현재는 단일 인스턴스·단일 ASGI 프로세스에서 분석 프로세스를 별도로 실행합니다.

GitHub Actions에서 파일 공개 검사·테스트·Docker 빌드를 수행합니다. 현재 저장소는 Render에 공개 URL로 연결되어 있어 **CI 통과 확인 후 수동 배포**합니다. Git provider 연결을 통해 자동 배포로 확장할 수 있습니다.

## 검증

- Python 테스트와 JavaScript 세션 테스트
- 실제 배포 서버에서 **파일 업로드 기반 분석 10종·조서 ZIP 다운로드** 확인
- 다른 방문자의 작업 접근 차단과 OpenDART 키 입력·비저장 처리 확인

[실행 기록](../docs/deployment-verification.json) · [테스트 코드](../tests/test_deployment.py) · [실제 서버 검증 스크립트](../scripts/smoke_demo.py)

## 다음으로 확장할 점

- **인증·권한** — Keycloak OIDC와 담당자·검토자 역할 도입
- **저장·실행** — PostgreSQL, 비공개 객체 저장소, 작업 큐로 분리
- **운영** — IP별 요청 제한, 저장량 상한, 지표·경보 개선
- **배포** — 의존성 취약점 검사와 CI 통과 기반 자동 배포 연결

위 항목은 현재 구현을 바탕으로 한 후속 개발 계획입니다.
