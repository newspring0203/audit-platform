# 프로젝트 구조와 책임

브라우저 입력·서비스 실행·Python 분석·검토 기록을 분리합니다. 학습 노트북은 같은 분석 함수를 직접 호출할 수 있습니다. 실행 예시는 [README](../README.md#실행-방법), 상세 API는 [backend-api.md](backend-api.md)를 참고합니다.

## 처리 흐름

```text
브라우저: 기능·조건·파일·자료 메모
  → FastAPI: 인증·소유권·조건·업로드 검증
  → 작업 저장소: 입력 버전·SQLite 메타데이터
  → 분석 자식 프로세스: 입력 해석 → 기능별 Python 함수
  → AnalysisResult: summary / tables / metadata
  → 원본 추적·검토 인덱스·조서 ZIP
  → 결과 조회·원본 확인·검토 기록 추가·다운로드
```

## 코드의 책임

| 위치 | 역할 |
|---|---|
| `frontend/` | HTML·CSS·JavaScript 입력·결과·검토 UI |
| `backend/app/main.py` | 앱·라우트 조립 |
| `backend/app/security.py`, `storage.py` | 인증·작업 소유권·임시 저장 |
| `backend/app/uploads.py`, `input_data.py` | 파일 구조·한도 검사, 파싱·원본 메타데이터 |
| `backend/app/jobs.py`, `worker.py` | 분석 프로세스·실행 상태·시간 제한 |
| `backend/app/analysis_dispatch.py` | 기능별 입력 슬롯·조건을 분석 함수로 전달 |
| `src/audit_data_lab/` | 웹과 독립적인 검증·전처리·분석·결과 모델 |
| `backend/app/reporting.py` | 엔진 해시·추적 정보·조서·ZIP |
| `backend/app/review_routes.py` | 원본 조회·자료 비교·기준 참조·검토 기록 |
| `notebooks/`, `outputs/` | 로컬 학습·결과. 웹 작업 TTL과 별개 |
| `tests/` | 분석·API·원본 추적·보안 경계·세션 검증 |

## 분석 엔진의 공통 계약

`AnalysisResult`는 name·summary·tables·metadata를 갖습니다. 입력 DataFrame을 복사해 변환하고 오류 코드·원본 행·조건·한계를 결과와 연결합니다. `common.py`는 컬럼·금액·날짜·GL 검증, `validation.py`는 구조화 오류, `review_service.py`는 실행·미실행 처리를 담당합니다.

금액은 Decimal 검사 후 100배 정수로 비교합니다. 통화·사업단위·연도·기간을 필요한 집계키에 포함합니다. 검증되지 않은 누락 금액·통화·기초수량을 정상값으로 만들지 않습니다. 일부 선행 검사는 즉시 중단하고 클렌징·일부 입력 검사는 여러 문제를 모읍니다.

## 결과·검토의 경계

실행 완료·하위 검사 상태·감사인 검토 완료는 별개입니다. 로그 기준 게이트가 실패하거나 선택적 TB·잔액·로트가 부적합하면 해당 검사만 미실행으로 남길 수 있습니다. 시스템·저장 장애 때 모든 산출물 생성을 보장하지는 않습니다.

원본 자료 버전·해시·행 연결·실행 조건을 결과에 붙이고 분석 시점 ZIP은 고정합니다. 이후 의견은 최신 검토 이력으로 별도 제공합니다. 결과 ID는 영구 거래키가 아니며 연결 상태가 unavailable인 항목도 있습니다. 서버 관리자에 대한 변경 불가능한 보관·전자서명은 구현 범위가 아닙니다.

## 인증·보관·외부 통신

로컬은 개발용 Bearer 토큰, 공개 데모는 방문자 쿠키 세션을 사용합니다. 작업 접근마다 소유권·만료를 확인하고 분석은 제한된 자식 프로세스에서 실행합니다. 작업 자료는 기본 1시간에 만료하며 서버 실행 중 정리합니다. 다운로드한 사본과 로컬 학습 결과는 이 TTL로 지우지 않습니다.

KYC의 OpenDART 수집과 선택적 AI 요약은 외부 통신입니다. 방문자 DART 키는 해당 실행에 일시적으로 전달하며 일반 조건·조서에 저장하지 않습니다. 고객 GL 분석과 공개 공시 전송의 경계를 구분합니다. 현재 배포·보안 조건은 [Backend README](../backend/README.md), [보관 정책](cache_and_retention.md), [KYC 보안](kyc_security.md)에 정리합니다.

기업용 SSO·담당자/승인자 역할·분리 저장소·외부 작업 큐·장기 조서 보관은 후속 과제입니다.
