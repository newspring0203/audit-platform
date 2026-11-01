# 공개 데모 배포와 검증

[웹 데모](https://audit-platform-ow3x.onrender.com/) · [Backend 구성](../backend/README.md) · [검증 기록](deployment-verification.json)

## 실행 모드

| 모드 | 서버·인증 |
|---|---|
| local | `scripts/run_local.py`, 127.0.0.1, 개발용 Bearer 토큰 |
| demo | `scripts/run_server.py`, 방문자별 세션·HttpOnly/Secure/SameSite 쿠키 |
| private | 지정 HTTPS 원점·운영자 발급 Bearer 토큰 |

공개 화면은 사용자 파일·분석 조건과 방문자 OpenDART 키를 입력받습니다. 상태 변경 요청에는 정확한 Origin과 `X-Audit-Request: 1`을 적용하며 작업 소유권·만료·요청 수·동시 실행·실행 시간을 검사합니다.

## 파일·키 처리

- 메타데이터·원본·결과는 `AUDIT_RUNTIME_ROOT`의 전용 작업 영역에 저장.
- 작업 생성 후 기본 3600초에 접근 만료, 서버 실행 중 30초 주기·시작 시 정리.
- OpenDART 키는 해당 실행 메모리에서 처리하고 결과에는 공시·조건·처리 상태를 기록.
- 일반 서버 이벤트는 기본 24시간 보관.
- 무료 서버의 휴면·재시작·재배포 시 작업과 세션이 조기에 소실될 수 있어 필요한 결과는 다운로드.

다운로드 사본과 인프라 백업은 각각의 보관 정책으로 관리합니다. [상세 보관 정책](cache_and_retention.md)

## Render 구성

1. Blueprint에서 저장소와 `render.yaml`을 연결합니다.
2. `Dockerfile`과 최소 의존성으로 이미지를 빌드합니다.
3. `AUDIT_MODE=demo`, 실제 HTTPS 원점, 플랫폼 포트·임시 저장 경로를 설정합니다.
4. 빌드·health·실제 서비스 주소와 배포 커밋을 확인합니다.

현재 서비스는 Render 무료 Docker Web Service, Singapore 지역의 단일 인스턴스입니다. 단일 ASGI 프로세스와 별도 분석 프로세스를 사용하고 이미지는 일반 사용자(uid 10001)로 실행합니다. 공개 저장소 URL 연결 방식이며 CI 확인 후 수동 배포합니다.

## 검증 명령

```bash
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend_session.test.mjs
python scripts/check_publication.py
python scripts/smoke_demo.py https://실제로-발급된-서비스-주소
```

검증은 합성 자료 업로드·분석 10종·조서 ZIP·방문자 격리·로그아웃·키 입력 경로를 확인합니다. GitHub Actions에서 공개 파일 검사·테스트·Docker 빌드를 수행하며 실제 실행 결과는 [검증 기록](deployment-verification.json)에 보관합니다.

## 공개 자료 관리

Git·Docker 공개 파일은 소스·설정·검토한 예제로 한정합니다. `.env`·토큰·`.runtime`·개인 원본·로컬 outputs는 별도 보관합니다. `check_publication.py`는 추적 파일의 경로·키 패턴과 XLSX 내부를 검사하며 자료 출처·개인정보는 파일별 검토에 연결합니다.

후속 운영 과제는 IP별 제한·외부 정리와 경보·조직별 권한·분리 저장소·CI 기반 자동 배포입니다.
