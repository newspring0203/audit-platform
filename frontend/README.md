# Audit Platform · Frontend

**회계 자료를 업로드하고, 분석 결과에서 원본과 검토 조서까지 확인하는 웹 워크스페이스입니다.**

**Audit Support Platform** 화면을 HTML · CSS · JavaScript로 구현하고 FastAPI에 연결했습니다.

[**웹에서 사용하기 ↗**](https://audit-platform-ow3x.onrender.com/) · [Backend](../backend/README.md) · [화면 설계](../docs/review_workspace.md)

## 구현한 기능

- **회사 이해** — 회사·기간별 OpenDART 공시 조회
- **데이터 처리** — SAP·QuickBooks 전처리, 사용자별 GL 분할, 데이터 클렌징
- **감사 데이터 분석** — 총계정원장 테스트, 분석적 검토, 자금 대사, 재고 분석, 조회 회신 비교
- **결과 검토** — 결과표, 원본 행 추적, 검토 메모와 조서 다운로드

## 사용 흐름

**기능 선택 → 조건 설정 → 자료 업로드 → 분석 실행 → 결과 검토 → 조서 다운로드**

1. **데모 시작**으로 작업 공간에 연결합니다.
2. 기능과 분석 조건을 선택하고 **분석 작업 만들기**를 누릅니다.
3. CSV·TXT·XLSX 자료를 업로드하고 **분석 실행**을 누릅니다.
4. 결과와 원본을 확인한 뒤 **분석 조서 ZIP**을 다운로드합니다.

KYC 공시는 회사와 조회 기간을 지정하고, 작업 화면에 본인의 [OpenDART 인증키](https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do)를 입력해 실행합니다. 키 입력란은 실행 요청 시 비워집니다. [키 처리 방식](../docs/backend-api.md#방문자-opendart-키-처리)

## 로컬에서 배포까지

| 구분 | 로컬 | Render 배포 |
|---|---|---|
| 접속 | `127.0.0.1:8000` | HTTPS 공개 주소 |
| 연결 | 개발용 토큰 입력 | 버튼으로 방문자 세션 발급 |
| 분석 | 사용자 조건·파일 입력 | 같은 입력 흐름 유지 |

로컬에서는 분석 화면과 API를 연결하고 파일 자동 업로드·원본 추적·검토 기록을 구현했습니다. 배포하면서 방문자 세션과 공개 이용 안내를 추가하고, 브라우저에 토큰을 직접 전달하던 절차를 줄였습니다.

작업 공간은 방문자별로 분리됩니다. 세션과 작업 자료는 각각 시작·생성 후 기본 1시간에 만료됩니다. 무료 서버의 휴면·재시작 때 자료가 먼저 삭제될 수 있으므로 필요한 결과는 다운로드합니다.

## 로컬 실행

저장소 루트에서 실행합니다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-deploy.txt
.venv/bin/python scripts/run_local.py
```

`http://127.0.0.1:8000`에서 **개발용 연결 설정**을 열고 `.runtime/reviewer.token`의 값을 입력합니다.

## 코드 구성

- [index.html](index.html) — 화면 구조와 입력·결과·검토 영역
- [workspace.css](workspace.css) — 스타일과 반응형 배치
- [workspace.js](workspace.js) — 파일 업로드, 분석 요청, 결과 표시
- [core/session.mjs](core/session.mjs) — 인증 상태와 요청 취소 처리

## 다음으로 개선할 점

- **입력 경험** — 업로드 미리보기와 컬럼 매핑 안내 개선
- **진행 상태** — 서버 준비·분석 대기·재시도 안내 보강
- **사용성** — 모바일 화면과 키보드 접근성 개선
- **협업 화면** — 로그인, 역할별 메뉴, 팀 검토 흐름으로 확장
