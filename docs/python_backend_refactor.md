# Python·백엔드 리팩터링

기존 API·노트북 import·분석 결과 형식을 유지하면서 책임을 분리했습니다.

## 백엔드에서 읽을 순서

| 파일 | 역할 |
|---|---|
| backend/app/main.py | 서버와 라우트를 조립하는 진입점 |
| backend/app/config.py | 환경변수·서버 설정. AppConfig는 main에서도 import 가능 |
| backend/app/security.py | 인증·요청 제한·공통 오류 처리 |
| backend/app/lifecycle.py | 시작·주기 정리·종료 |
| backend/app/http_helpers.py | 작은 JSON 요청 읽기·공통 응답 형식 |
| backend/app/job_routes.py | 작업 생성·조회·업로드·실행·다운로드·삭제 |
| backend/app/frontend_routes.py | 정적 파일과 CSP |
| backend/app/review_models.py | 자료 메모·기준서·검토 기록 입력 검증 |
| backend/app/review_support.py | 소유권 확인·검토 파일 읽기/쓰기 |
| backend/app/review_routes.py | 원본 조회·자료 비교·기준서·검토 기록 API |
| backend/app/worker.py | 분석 자식 프로세스 진입점 |
| backend/app/input_data.py | 파일 해시·형식·크기 검사와 파싱 |
| backend/app/analysis_dispatch.py | 기능별 입력 조건 확인·분석 함수 호출 |
| backend/app/reporting.py | 추적 정보·조서·ZIP 생성 |

main.py는 247행에서 44행, worker.py는 99행에서 35행으로 정리했습니다. 새 파일은 각 역할을 담당하며 진입점만 짧게 만든 것입니다. 설정값·토큰 유효기간·소유권·삭제·다운로드 정책을 변경한 작업은 아닙니다.

## Python 분석 코드

- analytics.py: 연도 비교, 월별 비교, 기간 범위 확인, 선택적 TB 검토를 별도 함수로 나눴습니다.
- cash.py: 입력 준비, 후보 구성, 상호 유일 연결, 미대사 검토를 나눴습니다.
- cash_balances.py: 제출 잔액·조정액의 산술 대사를 분리했습니다.
- result.py: AnalysisResult와 JSON/CSV 출력을 분리했습니다. 기존 common 및 패키지 import 경로는 유지합니다.
- analysis_notes.py: 긴 조서 설명 문구를 모았습니다. 계산 코드와 설명 텍스트를 따로 읽을 수 있습니다.

설명은 모두 지우지 않았습니다. 금액·통화 기준, 미실행 이유, 원본 행 번호, 검토 한계와 보안상 중요한 이유는 유지했습니다. 계산 결과에 제공되는 설명도 기존 값을 보존했습니다. JET·재고·KYC 등 모든 분석 내부를 새로 작성한 것은 아닙니다.

## 검증

변경 전 합성 입력으로 7개 기능의 요약·표·추적 결과 ID를 저장하고 변경 후 동일한 내용인지 비교했습니다. 분석값과 원본 연결 ID는 모두 일치했습니다. 코드 변경으로 엔진 코드 해시는 달라집니다.

- Python 전체 테스트: 185개 통과. 실제 자식 프로세스·업로드·조서·ZIP·사용자 격리·삭제 검증 포함.
- 프론트엔드 인증 테스트: 13개 통과.
- API 등록 기능과 분석 실행기 등록 기능이 일치하는지 확인하는 검사를 추가했습니다.
- 실제 로컬 실행 명령으로 서버 시작·health·인증 API·프론트엔드 모듈 응답을 확인했습니다.

모듈 분리 중 표준 라이브러리 http와의 이름 충돌을 발견하여 http_helpers.py로 수정했습니다. 자식 프로세스에서도 동일하게 동작하도록 확인했습니다.

## 반영 방법

기존 서버를 Ctrl+C로 종료한 뒤 프로젝트 루트에서 다시 실행합니다.

```bash
.venv/bin/python scripts/run_local.py
```

브라우저를 새로고침하고 토큰으로 연결합니다. 기존 완료 결과를 새로 계산하지 않으며, 변경된 코드로 분석하려면 새 작업을 실행하세요. 사용자 원본·기존 조서·기존 학습 노트북은 수정하지 않았습니다.
