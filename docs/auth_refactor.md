# 인증·세션 리팩터링 1차

세션·요청 처리를 공통 모듈로 분리하고 재연결·로그아웃 경합을 정리했습니다.

## 적용 범위

- `frontend/core/session.mjs`: 메모리 토큰, 세션 epoch, 후보 토큰 검증, 공통 JSON/Blob 요청, AbortController, 세션 타이머, 로그아웃.
- `frontend/workspace.js`: 위 모듈을 사용하고 화면 generation·작업 ID·선택 행·페이지 offset으로 늦은 화면 응답을 걸러냅니다.
- `frontend/index.html`: type=module로 로딩합니다.
- `backend/app/frontend_routes.py`: 고정된 `/core/session.mjs` 정적 경로를 제공합니다. 기존 CSP의 script-src/connect-src self를 유지합니다.
- `tests/frontend_session.test.mjs`: 독립적인 세션·요청 회귀 테스트.

유효한 연결이 있을 때 잘못된 후보 토큰을 입력해도 기존 연결과 분석 결과는 유지합니다. 정상 후보를 검증한 뒤에만 새 세션으로 전환합니다. 같은 토큰 재연결도 새 epoch으로 구분합니다.

401은 공통 UNAUTHENTICATED 응답으로 처리합니다. 현재 세션의 401만 연결을 초기화하고 재확인을 안내합니다. 늦은 401은 해당 요청 epoch과 대조해 처리합니다. 다운로드도 같은 처리를 사용합니다.

폴링·자동 저장 타이머와 진행 중인 요청은 세션 변경 시 취소합니다. 자동 저장의 큐와 상태 맵은 새 세션으로 분리하고, 현재 세션의 UI 응답만 반영합니다. 요청 취소 후 서버 반영 상태는 작업 재조회로 확인합니다.

로그아웃은 로컬 세션을 먼저 해제하고 캡처한 이전 토큰의 서버 폐기를 요청합니다. 서버 폐기 응답은 요청한 세션과 연결해 상태를 표시합니다.

## 검증

- JavaScript 인증·세션 테스트 13개 통과: 잘못된 재연결, 동시 연결, 같은 토큰 재연결, 늦은 401/본문/Blob, 요청 취소, 타이머 취소, 로그아웃 경합, 헤더·캐시 정책.
- Python 전체 테스트 184개 통과.
- 실제 로컬 FastAPI: 모듈 경로·JavaScript MIME, 정상 로그인, 실패한 재연결 이후 작업 조회, 공통 모듈의 ZIP 다운로드, 로그아웃 후 기존 토큰 거절 확인.
- 실제 브라우저(IAB): 정상 연결·결과 조회, 잘못된 재연결 시 기존 결과 유지, 서버에서 폐기한 토큰의 401 안내·화면 초기화 확인.

## 적용 후 실행

서버 재시작과 브라우저 새로고침으로 정적 경로 변경을 반영합니다.

```bash
cd /Users/saebom/audit-platform
.venv/bin/python scripts/run_local.py
```

실행 중인 기존 서버는 그 터미널에서 Ctrl+C로 종료한 뒤 위 명령을 실행합니다. 브라우저는 Cmd+Shift+R 후 토큰을 다시 입력합니다. 기본 토큰 유효기간 1시간·작업 소유권 정책을 유지하고 개발용 토큰은 메모리에 보관합니다.

## 테스트 재실행

```bash
node --test tests/frontend_session.test.mjs
.venv/bin/python -m unittest discover -s tests -q
```

## 다음 범위

후속 리팩터링은 작업·자료 관리·검토 화면 렌더링의 책임 분리를 중심으로 진행합니다.
