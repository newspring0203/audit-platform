# KYC 실제 API 연결

## 먼저 OpenDART 수집만 실행

1. 프로젝트 루트의 `.env`를 VS Code에서 엽니다.
2. `DART_API_KEY=` 뒤에 본인이 발급받은 40자리 키를 직접 넣고 저장합니다. 채팅·노트북·스크린샷에 키를 넣지 마세요.
3. `notebooks/kyc_opendart.ipynb`에서 설정 셀을 실행하고 `RUN_LIVE=True`, `USE_AI=False`로 수집을 실행합니다.

터미널에서도 프로젝트 루트에서 실행할 수 있습니다.

```bash
python scripts/run_kyc.py --check-config
python scripts/run_kyc.py --find-company 회사명일부
python scripts/run_kyc.py --company 선택한DART고유번호 --max-reports 1
```

현재 프로젝트는 기존 `/Users/saebom/ADS/.venv/bin/python` 환경으로 테스트했습니다. 위 명령의 python 대신 해당 실행 파일 경로를 사용할 수 있습니다. 새 API 연결은 Python 표준 라이브러리로 작성하여 추가 설치가 필요하지 않습니다.

## AI 연결

OpenAI API 키가 준비되면 `.env`의 `OPENAI_API_KEY`, `OPENAI_MODEL`도 설정합니다. 모델은 본인 계정에서 사용할 수 있고 Responses API의 구조화 출력을 지원하는 ID를 직접 선택합니다. 현재 기본 모델을 임의로 지정하지 않았습니다.

```bash
python scripts/run_kyc.py --find-company 회사명일부
python scripts/run_kyc.py --company 선택한DART고유번호 --max-reports 1 --with-ai
```

기본 실행은 공시 수집만 합니다. `--with-ai` 또는 노트북의 USE_AI=True에서만 OpenAI API 호출이 발생하며 API 사용 요금이 발생할 수 있습니다. ChatGPT/Codex 로그인으로 키를 대체하지 않습니다. 모델 접근 권한·결제·실제 인증은 본인의 계정에서 확인해야 합니다.

## 결과와 해석

- 공개 공시 ZIP·텍스트: `data/raw/dart/<실행ID>/`.
- 출처·요약·근거·메타데이터: `outputs/kyc/<실행ID>/`.
- sources.csv: 회사 고유번호, 접수번호, 원문 링크, 원문 SHA-256, 문자 수.
- insights.csv: 회사이해·위험후보·추가확인, 후속 검토, 미검토 상태.
- evidence.csv: 요약별 원문 근거와 링크.
- summary.json: 조회 조건, AI 모델, 선택 발췌문 위치·문자 수·비율.

공시 제목·접수일만 요약하지 않고 document.xml 원문을 내려받아 텍스트를 추출합니다. 현재는 사업보고서(A001), 최종보고서(last_reprt_at=Y), 최근 순, 최대 5건까지 지원합니다. 회사명은 회사 목록에서 정확히 식별하며 임의로 유사 회사 하나를 고르지 않습니다.

AI는 전체 공시가 아닌 키워드로 선택한 최대 18,000자의 발췌문을 읽습니다. 1회 요청, 출력 최대 2,200토큰이며 자동 유료 재시도는 하지 않습니다. 전송 자료는 이 파이프라인이 수집한 공개 공시입니다. 원본 GL·고객 내부 자료는 전달하지 않습니다. 발췌 범위는 보고서에 남기며, 관련 내용이 선택되지 않았을 수 있습니다. 따라서 위험이 없다는 결론을 내리지 않습니다.

JSON 구조화 출력 외에도 출처·청크 ID·근거 문구의 원문 일치를 로컬에서 검증합니다. 이는 요약의 의미상 정확성이나 감사 결론을 보증하지 않으며 감사인의 원문 확인이 필요합니다. 본문 속 명령은 데이터로 취급하고 도구 실행에 사용하지 않습니다.

키·요청 URL·외부 서버의 원문 에러 메시지를 결과에 기록하지 않습니다. 인증 실패·요청 한도·빈 공시·다른 회사·응답 거절·불완전 응답·근거 불일치는 DataValidationError 형식으로 안내합니다.

.env는 기존 환경변수를 덮어쓰지 않습니다. VS Code 노트북에서 키를 바꿨는데 반영되지 않으면 커널을 재시작하세요. 현재는 KEY=value와 단순 따옴표만 지원하며 셸 명령과 변수 치환은 실행하지 않습니다.

## 검증 범위

API 응답 모양을 재현한 테스트로 연결 로직을 검증했습니다. 실제 인증키가 로컬에 설정되기 전에는 실시간 수집 성공이나 실제 AI 요약 성공으로 표시하지 않습니다.

## 공식 문서

- [OpenDART 공시 검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)
- [OpenDART 회사 고유번호](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018)
- [OpenDART 원문 파일](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003)
- [OpenAI 구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)

특정 기업은 기본 선택되어 있지 않습니다. 보안·웹 연결 요구사항은 `kyc_security.md`를 참고하세요.

## AI 없이 주제별 원문 검토자료 보기

새 작업의 기본 결과는 `review_passages`입니다. 사업 내용, 매출·매출채권, 재고, 자금·차입, 우발부채·약정, 특수관계자별로 키워드가 등장하는 본문 후보를 최대 한 건씩 찾습니다. 짧은 목차보다 설명 본문이 이어지는 위치를 우선합니다. 발췌는 원문 그대로이며 확인할 질문과 연결기능은 미리 작성한 검토 안내입니다. AI 요약이나 위험 판단이 아닙니다.

섹션명은 추출 텍스트에서 추정하며, 원문 위치는 저장된 텍스트의 0부터 시작하는 [시작문자, 끝문자)입니다. 섹션 오인식, 관련 본문 누락, 표 문맥 손실이 가능하므로 공시 원문과 대조하세요. 미확보는 해당 사항이 없다는 결론이 아닙니다. 기존 작업 결과는 변경되지 않으므로 서버 재시작·화면 새로고침 후 새 작업을 실행하세요. `sources`는 출처·원문 식별 정보이며 표지 500자 미리보기는 제거했습니다.
