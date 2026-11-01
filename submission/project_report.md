# Audit Platform: 원본과 검토 근거를 연결하는 감사 지원 도구

작성 상태: 제출용 초안 / 로컬 MVP / 2026-10-31
GitHub 및 시연 영상 URL은 실제 공개 후 추가합니다.

## 1. 개발 목적

감사 데이터의 전처리, 반복적인 전표 검사, 자료 비교와 결과 문서화 작업을 지원하는 플랫폼을 구현했다. 분석 숫자만 제공하는 데서 나아가, 사용자가 결과의 입력 자료·원본 행·조건을 확인하고 검토 의견과 증빙 참조를 기록할 수 있도록 구성했다.

개발의 출발점은 AICPA Audit Data Standards Python Example의 SAP·QuickBooks·groupby 학습 예제였다. 기존 학습용 코드는 보존하고 별도 audit-platform 프로젝트에서 함수·검사·서비스 계층을 확장했다. 학습 예제와 직접 확장한 구현을 구분해 정리했다.

## 2. 업무 문제와 해결 방향

| 업무 문제 | 구현 방향 |
|---|---|
| CSV 출력과 콘솔 메시지만으로는 웹에서 결과를 다루기 어려움 | DataFrame·요약·메타데이터를 반환하는 공통 결과 형식 |
| 오류가 나면 실행이 끝나 원인을 찾기 어려움 | 오류 코드·필드·원본 위치·설명·후속 검토를 결과로 제공 |
| 결과 수치를 복사하면 원본과 계산 조건이 분리됨 | 자료 해시·버전·결과 ID·원본 행 연결 |
| 시점·자료 버전 혼동 | 기간과 PBC 참조 등록, 이전 버전 비교 |
| 금액·통화 기준 미확보 상태에서 대사하면 잘못된 결론 가능 | 기준 미확보와 미실행을 차이 없음과 구분 |
| 여러 기능과 검토 단계가 긴 화면에 섞임 | 왼쪽 기능 내비게이션, 자료 준비·분석 결과·검토 기록 탭 |

## 3. 시스템 구조

브라우저 HTML/CSS/JavaScript → FastAPI 작업 API → 별도 프로세스의 Python 분석 엔진 → 작업별 비공개 임시 저장소 → 결과 조회 및 다운로드.

분석 엔진은 pandas 기반이며 결과 표·요약·메타데이터를 공통 형식으로 반환한다. 파일 처리·작업 실행·조회·검토 기록·다운로드는 서버에서 연결한다. 고객 파일은 전용 작업 저장소에 보관한다. 프론트엔드는 기존 기능을 재사용하는 가벼운 구조로 작성했다.

## 4. 구현 기능

- JET: 규칙별 전표 탐지, 복합 조건 후보, 선정 이유·후속 확인 안내. 웹 로그 대사는 근거 승인 연결 전까지 미실행으로 구분한다.
- 분석적 검토: 연도·월별 GL 비교, TB 잔액 비교, 분류·부호 기준이 있을 때 재무비율 초안 계산.
- Cash Proofing: 계좌·통화·부호 금액·시차의 유일 후보 대사, 중복 후보·미대사 경과일·제출 잔액 조정 검토.
- 재고: 기말·기간 중 음수 수량, 미출고 후보, 월별 수불과 대사된 로트 수량의 연령 집계.
- 클렌징: 결측·중복·날짜·금액 검사, 명시적 컬럼 매핑과 충돌 확인.
- KYC: OpenDART 수집·AI 요약 연결 코드, 출처 검사, 요약 실패 시 근거 보존. 실제 API 키 실행 검증은 미완료.
- GL 사용자별 분할: groupby 기반 행 분할, 사용자 누락 별도 보관, 원본 행 추적과 ZIP 출력.
- QuickBooks: 기존 예제 형식의 원본 보고서 평탄화. 미분류·거부 행과 평탄화 상태를 기록한다.
- 조서: CSV·JSON·Markdown 초안, 렌더러 설정 시 Excel. 후속 검토 이력은 분석 시점 ZIP과 별도 내려받는다.

SAP 원본 → GL·TB 변환은 노트북과 웹 API에서 실행하며 예제 필드명·달력연도·금액 정밀도를 확인한다.

## 5. 원본 추적과 판단 기록

업로드 파일 해시·자료 버전·논리 원본 행·실행 조건·엔진 코드 해시를 기록한다. 결과별 고유 ID를 웹과 CSV에 연결한다. 집계 입력 범위 연결과 단일 행 연결을 구분하고, 연결 미구현 결과를 명시한다. 추적 시작점은 이번 작업에 업로드한 자료이며 SAP 변환은 BSEG·BKPF 원본 행을 연결한다.

검토자는 사실·증빙/PBC 참조·결론·기준서 판본/문단/적용 사유를 기록한다. 이력은 추가 방식으로 저장하고 revision 충돌을 확인한다. 기준서 참조는 사용자가 등록하고 검토 기록에 연결한다.

## 6. 보안과 보관 범위

개발용 Bearer 인증, 사용자·회사 소유권 검사, 다운로드 권한 확인, 작업 만료와 삭제, no-store 응답을 구현했다. 토큰은 브라우저 메모리에만 둔다. KYC 키는 별도 실행 요청에서 처리하고 파일은 내부 식별자로 저장하며 CSV 수식 방지 처리를 적용한다.

정식 SSO/OIDC, 조직 공유 권한, TLS 배포 구성, 암호화 보관·백업/삭제 운영 정책은 향후 작업이다.

## 7. 검증과 한계

직전 전체 테스트는 182개가 통과했다. 추가한 화면 개편은 기존 검토 API 회귀 검사, JavaScript 문법 검사, 합성 자료를 이용한 브라우저 기능 메뉴·결과 탭 동작으로 확인했다. 검증 자료는 합성 예제이며 실행별 결과를 기록했다.

화면의 숫자·차트는 후속 검토 대상과 근거를 보여준다. 감사인은 기준·모집단·증빙을 확인하고 검토 의견을 기록한다.

## 8. 시연과 후속 개발

시연은 합성 GL을 사용해 자료 업로드 → 분석 → 결과 비교 → 원본 조회 → 검토 기록 → 다운로드를 보여준다. 구현된 기능과 향후 계획을 분리해 설명한다.

후속 우선순위는 실제 파일 다양성 검증, 기능별 Excel 구성, KYC 실행 검증과 역할별 권한·운영 보관 체계다.

## 9. 실제 실행한 데이터 변환 사례

다음 표는 합성 원본과 실제 Jupyter 실행 결과에서 추출했다. 파일을 손으로 변환해 만든 결과가 아니라 `demo_walkthrough_executed.ipynb`의 저장된 출력이다. 전체 셀과 중간 출력은 [실행 결과 HTML](evidence/demo_walkthrough.html) 및 노트북에서 확인한다.

### 9.1 QuickBooks 계층형 보고서 → 거래 표

원본 일부 열:

| Account heading | Type | Date | Num | Amount |
| --- | --- | --- | --- | --- |
| — | Type | Date | Num | Amount |
| DEMO Cash | — | — | — | — |
| — | Deposit | 2026-10-15 | 0001 | 5000 |
| Total Cash | — | — | — | 5000 |
| DEMO Sales | — | — | — | — |
| — | Invoice | 2026-10-15 | 0001 | -5000 |

변환 후:

| QuickBooks_Source_Row | Account_Source_Row | Account Description | Date | Num | Amount | ADS_Status |
| --- | --- | --- | --- | --- | --- | --- |
| 3 | 2 | DEMO Cash | 2026-10-15 | 0001 | 5000 | not_converted |
| 6 | 5 | DEMO Sales | 2026-10-15 | 0001 | -5000 | not_converted |

계정 표제 행을 실제 거래에 연결한 위치를 Account_Source_Row에 남기고 합계 행은 별도 처리 이력으로 기록했다. Num은 원본 문서번호로 보존하고 ADS 매핑 전 상태는 ADS_Status=not_converted로 기록했다.

![QuickBooks 원본](evidence/quickbooks_before.png)

![실제 변환 결과](evidence/quickbooks_after.png)

### 9.2 컬럼 이름 변경과 값 검사의 분리

| 전표번호 | 계정번호 | 거래일자 | 금액 | 입력자 |
| --- | --- | --- | --- | --- |
| DEMO01 | 1000 | 20261001 | 1000 | DEMO_A |
| DEMO02 | 4000 | 20260230 | oops | DEMO_B |
| DEMO02 | 4000 | 20260230 | oops | DEMO_B |
| DEMO03 | — | — | 200 | — |

사용자 지정 매핑 후:

| Journal_ID | GL_Account_Number | Effective_Date | Amount | Entered_By |
| --- | --- | --- | --- | --- |
| DEMO01 | 1000 | 20261001 | 1000 | DEMO_A |
| DEMO02 | 4000 | 20260230 | oops | DEMO_B |
| DEMO02 | 4000 | 20260230 | oops | DEMO_B |
| DEMO03 | — | — | 200 | — |

계정번호→GL_Account_Number, 거래일자→Effective_Date 등 이름은 바뀌었지만 20260230과 oops는 그대로 남는다. 오류 7개와 중복 관련 행 2개를 별도 결과로 제공한다. 컬럼 매핑과 값 검증을 각각 확인하는 사례다.

### 9.3 GL 행 → 계정별 전년 비교

| GL_Account_Number | Amount_Currency | Current_Movement | Prior_Movement | Change | Change_Pct |
| --- | --- | --- | --- | --- | --- |
| 1000 | KRW | 7000.0 | 3000.0 | 4000.0 | 133.33333333333331 |
| 4000 | KRW | -7000.0 | -3000.0 | -4000.0 | -133.33333333333331 |

두 연도와 사업단위·계정·통화별로 순변동을 집계했다. 매출 계정의 부호는 입력 D/C 정의를 따라 집계하고 변동 원인은 원본·증빙 검토로 연결한다.

### 9.4 코드와 실행 결과의 연결

아래는 실제 `src/audit_data_lab/gl_split.py`에서 가져온 코드 일부다. GitHub 공개 후 같은 파일의 고정 커밋 링크를 보고서에 추가한다.

```python
    grouped=gl.groupby(keys,sort=False,dropna=False).indices
    for number,(key,positions) in enumerate(grouped.items(),start=1):
        unassigned=pd.isna(key)
        positions=list(positions)
        name=f'user_{number:04d}' if not unassigned else 'unassigned_user'
        frame=gl.iloc[positions].copy()
        frame.insert(0,'Split_Source_Row',[pos+2 for pos in positions])
        tables[name]=frame
```

실제 결과는 사용자 3그룹, 입력 6행·출력 6행이다. 원본을 보존하고 CSV 저장 시 수식 방지 정책을 적용한다.

관련 코드 경로:
- `src/audit_data_lab/quickbooks.py`: 계정 연결·날짜/금액 검증·행 처리 이력
- `src/audit_data_lab/column_mapping.py`: 명시적 컬럼 이름 매핑
- `src/audit_data_lab/analytics.py`: 연도/기간별 순변동 비교
- `src/audit_data_lab/traceability.py`: 결과 ID와 원본 행 연결
- `backend/app/worker.py`: 파일 읽기·분석·조서 생성

검증 수치는 [실행 체크 기록](evidence/executed_checks.json)과 연결한다. 해당 기록은 합성 시연의 실행 범위를 담는다.

추가 확인: 같은 합성 GL/TB와 QuickBooks Excel을 실제 로컬 HTTP API에 업로드하여 실행 및 ZIP 다운로드까지 확인했다. 상세 검증은 [웹 실행 체크](evidence/web_demo_checks.json)에 기록했다. 화면 관련 회귀 검사 29개가 통과했으며 연결 입력·버튼 높이 42px, 검토/참조 저장 버튼 높이 40px과 페이지 가로 넘침이 없음을 브라우저에서 확인했다.

## 10. 기능별 일괄 검증과 기준서 선택 개선

최종 전체 테스트 184개가 통과했다. 7개 로컬 분석 기능은 합성 시연 파일을 업로드하여 분석·결과 조회·ZIP 다운로드·복수 기준서 참조 연결·검토 이력 내보내기를 검증했다. 브라우저에서도 참조 등록과 체크박스 선택·저장이 연결됨을 확인했다. 등록 항목이 없는 선택 상자는 빈 상태 안내와 등록 이동 버튼으로 대체하고, 등록 후에는 복수 체크박스를 제공하도록 개선했다.

KYC는 모의 공시로 처리 경로를 검증했다. 자세한 범위는 [검증 기록](evidence/demo_suite_verification.json)에 남겼다.

## 11. 자동 업로드와 기간 구분

파일 선택 시 업로드하고 자료 메모 기간·PBC 변경 후 자동 저장하도록 개선했다. 여러 슬롯은 순차 처리하며 저장 중·실패·기간 미완성 시 분석 실행을 막는다. GL 연도 비교와 TB 특정 회계기간 비교를 자료 메모 날짜와 분리 표시한다. 실제 브라우저에서 파일 선택·후속 메타데이터 수정 저장·불완전 기간의 실행 차단·저장 후 재활성화를 확인했다. 관련 회귀 검사 34개가 통과했다.

## 13. Python·백엔드 책임 분리

설정·보안·라우트·작업 입력·분석 선택·조서 출력을 분리하고 Python 분석적 검토와 자금 대사를 단계별 함수로 정리했다. 긴 조서 설명은 analysis_notes.py에 모았으며 필수 검토 정보는 보존했다. 기존 API와 AnalysisResult import를 유지했다. 합성 입력 7개 기능의 변경 전후 요약·표·원본 연결 ID가 일치했으며 전체 Python 검사 185개와 프론트엔드 인증 검사 13개를 통과했다. 구조와 검증 범위는 docs/python_backend_refactor.md에 기록했다.
