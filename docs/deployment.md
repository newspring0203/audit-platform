# 공개 데모 배포와 검증

## 인증과 데이터 경계

- local: `scripts/run_local.py`, 127.0.0.1, 편집기로 확인하는 개발용 Bearer 토큰.
- demo: `scripts/run_server.py`, 방문자별 무작위 세션, HttpOnly·Secure·SameSite=Strict·__Host- 쿠키. 토큰 값은 JSON이나 프론트엔드 JavaScript에 전달하지 않는다.
- private: HTTPS 원점을 명시하는 운영자 발급 Bearer 토큰. 기업용 사용자 관리·SSO는 별도 구현 대상.
- 상태 변경 요청은 정확한 Origin과 `X-Audit-Request: 1`을 모두 검사한다. CORS를 열지 않는다.
- demo의 업로드 API·SAP·KYC를 차단하고 서버 소유 합성 샘플과 고정 조건만 실행한다. API 키를 데모에 등록하지 않는다.
- 사용자별 작업 접근 검사, 세션 만료·폐기, 요청 수·세션 수·작업 수·분석 시간 제한을 적용한다. 익명 공개 데모는 공격 방어용 서비스가 아니며 대규모 사용에는 별도 WAF/인증이 필요하다.

## 파일 정책

SQLite 메타데이터와 파일은 `AUDIT_RUNTIME_ROOT`에만 저장하고 정적 파일로 제공하지 않는다. 원본·결과는 작업 생성 후 기본 3600초에 접근을 차단한다. 실행 중인 서버가 30초 간격으로 만료 작업을 삭제하고 시작 시에도 정리한다. 로그에는 원본 내용·키·토큰을 남기지 않는다. 일반 서버 이벤트는 기본 24시간 후 정리한다.

Render 무료 환경의 로컬 디스크는 임시 저장소이다. 휴면·재시작·재배포 시 세션과 작업이 먼저 없어질 수 있다. 쿠키가 남아 있더라도 새 서버가 이를 인증하지 못하면 데모 시작으로 새 세션을 생성한다. 사용자 브라우저로 다운로드한 파일은 서버가 삭제할 수 없다.

## Render 배포

1. Render 계정으로 로그인하고 New → Blueprint를 선택한다.
2. `newspring0203/audit-platform` 저장소, `main` 브랜치, `render.yaml`을 연결한다.
3. 무료 플랜인지 확인한 뒤 배포한다. 저장소에는 배포에 필요한 Dockerfile과 최소 의존성이 포함되어 있다.
4. `RENDER_EXTERNAL_URL`이 실제 HTTPS 원점이다. 다른 서비스나 사용자 도메인은 `AUDIT_PUBLIC_ORIGIN`을 정확히 설정한다.
5. 배포 로그의 빌드·health 성공과 서비스의 실제 URL을 확인한다.

단일 ASGI 프로세스·단일 인스턴스를 사용한다. 다중 프로세스에서 같은 SQLite/작업 저장소를 공유하지 않는다. 분석 프로세스만 기본 1개까지 실행한다. Docker 이미지는 일반 사용자(uid 10001)로 실행하고, 허용된 소스와 합성 샘플만 복사한다.

## 검증

```bash
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend_session.test.mjs
python scripts/check_publication.py
python scripts/smoke_demo.py https://실제로-발급된-서비스-주소
```

마지막 명령은 실제 서버에서 9개 분석 실행·조서 ZIP 무결성·다른 방문자의 접근 차단·로그아웃·업로드 및 외부 API 차단을 확인한다. HTTPS URL은 발급된 주소로 교체한다. 코드에 가상의 배포 성공이나 URL을 기록하지 않는다.

GitHub Actions에서도 보안 경로 검사·Python/브라우저 세션 테스트·Docker 빌드를 실행한다. 로컬 Docker Desktop이 꺼져 있으면 이미지 빌드는 Docker 실행 후 또는 CI/Render에서 검증해야 한다.

## 공개 전 점검 범위

`.env`, `.runtime`, 토큰 파일, 원본/가공 실자료, outputs, 노트북, 사적 증거 자료는 Git 및 Docker에서 제외한다. `check_publication.py`는 Git 추적 파일의 금지 경로·일반 키 패턴·XLSX 내부 키 패턴을 검사한다. 이는 임의의 모든 개인정보를 자동 판별하는 검사는 아니므로, 데이터 파일은 검토한 합성 자료 폴더만 명시적으로 추가한다.

원래 로컬 키와 토큰 값의 포함 여부는 공개 이력 전체를 별도로 대조하며 값 자체는 출력하지 않는다. 배포 후 실제 URL과 검증 결과를 README 및 `docs/portfolio/links.json`에 반영한다.

## 이번 공개 배포

- 서비스: https://audit-platform-ow3x.onrender.com
- Render 무료 Docker Web Service, Singapore 지역, 단일 인스턴스.
- GitHub 공개 저장소 URL로 연결했으며 추가 저장소 접근 권한은 부여하지 않았다.
- 설정된 환경변수는 AUDIT_MODE=demo이며 외부 API 키는 등록하지 않았다.
- 최초 배포 코드: 96cc85624e718d2af7a1d5c1c9d049f6ec4da05e. 이후 README 제거 커밋은 실행 코드에 영향을 주지 않는다.
- 공개 저장소 직접 연결 방식에서 변경 반영 여부는 Render의 배포 커밋을 확인한다. 필요하면 Manual Deploy → Deploy latest commit으로 반영한다.
- README는 사용자가 직접 작성하기로 하여 공개 저장소에서 제거했다. 배포 주소는 이 문서와 links.json에 기록한다.

## 검증 결과 (2026-10-31)

- Python 181개 검사 실행: 성공, 비공개 노트북 대조 2개 건너뜀.
- JavaScript 세션 검사 15개 성공.
- GitHub Actions의 동일 검사 및 Docker 이미지 빌드 성공: https://github.com/newspring0203/audit-platform/actions/runs/41197318381
- 공개 Git 추적 파일 금지 경로·키 패턴 검사 통과. 업로드 전 188개 Git 이력 blob과 실제 로컬 키·토큰 값 2개를 대조해 일치 0건 확인. 비밀 값은 출력하지 않았다.
- 실제 공개 HTTPS 서버에서 분석 9종 실행·조서 ZIP 무결성·다른 방문자 작업/다운로드 404·CSRF 403·파일 업로드 403·KYC 차단·로그아웃 후 401 확인.
- 공개 분석 결과 요약과 ZIP 크기: [deployment-verification.json](deployment-verification.json).

검증은 합성 자료와 현재 코드 범위에 대한 기능·보안 경계 확인이며, 모든 취약점 부재를 보증하는 외부 보안 감사는 아니다.
