# KYC 공시 수집과 선택적 AI 요약

## OpenDART 설정·실행

1. 로컬 `.env`에 본인의 40자리 `DART_API_KEY`를 저장합니다.
2. 회사 후보를 검색하고 8자리 DART 고유번호를 선택합니다.
3. 조회 기간·공시 유형·보고서 수를 지정해 실행합니다.

```bash
python scripts/run_kyc.py --check-config
python scripts/run_kyc.py --find-company 회사명일부
python scripts/run_kyc.py --company 선택한DART고유번호 --max-reports 1
```

웹에서는 작업 화면에 본인 OpenDART 키를 입력해 실행합니다. 키는 해당 작업 메모리에서 일시적으로 처리합니다. [키 전달·보관](kyc_security.md)

## AI 요약 설정

서버의 `OPENAI_API_KEY`, `OPENAI_MODEL`과 웹 AI 허용 설정을 준비합니다. 모델은 계정에서 사용할 수 있는 Responses API 구조화 출력 지원 ID를 지정합니다.

```bash
python scripts/run_kyc.py --company 선택한DART고유번호 --max-reports 1 --with-ai
```

기본 실행은 공시 수집이며 `--with-ai`에서 유료 AI 호출이 발생합니다. 공개 공시 중 키워드로 선택한 최대 18,000자, 요청 1회·출력 최대 2,200토큰 범위로 처리합니다. 발췌 위치·범위와 AI 실행 상태를 결과에 기록합니다.

## 공시·결과 구조

| 자료 | 역할 |
|---|---|
| 원문 ZIP·추출 텍스트 | CLI 기준 `data/raw/dart/<실행ID>/` |
| 결과표·메타데이터 | CLI 기준 `outputs/kyc/<실행ID>/` |
| `sources` | 공시 문서 ID·접수번호·회사·URL·해시·문자 수 |
| `review_passages` | 사업·채권·재고·자금·약정·관계자별 문단 후보 |
| `insights`, `evidence` | 선택적 AI 요약과 원문 인용·출처 연결 |
| `summary.json` | 조회 조건·처리 상태·발췌 범위 |

사업(A001)·반기(A002)·분기(A003) 보고서를 최근 순·최종보고서 기준으로 최대 5건 수집합니다. 주제별 탐색은 문서·주제당 최대 한 건의 본문 후보를 선정하며 확보 상태와 원문 위치를 제공합니다.

`review_passages.Source_ID → sources.source_id`는 N:1 관계입니다. 문자 위치는 추출 텍스트의 0부터 시작하는 `[시작, 끝)`입니다. 검토자는 원문 링크에서 문맥을 확인하고 의견을 기록합니다.

## 원본 식별·검증

`document_sha256`는 OpenDART에서 수신한 원문 ZIP 전체 바이트의 SHA-256입니다. 이전 해시와 대조해 원본 동일성을 확인하며 본문 변경은 추출 텍스트 비교로 확인합니다.

AI 결과는 출처·청크 ID·인용문의 원문 존재를 검증합니다. 입력 공시 본문은 데이터로 취급하며 결과는 미검토 상태로 제공합니다. 키·공급자 URL·상세 오류는 공통 오류 코드로 처리합니다. AI 실패 시 수집 공시와 검토 문단을 유지합니다.

연결 테스트는 모의 API 응답을 사용하고 실제 호출은 실행별 상태와 기록으로 확인합니다. `.env`는 KEY=value 형식으로 읽으며 키 변경 후 노트북 커널을 재시작하면 설정이 반영됩니다.

## 공식 문서

- [OpenDART 공시 검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)
- [OpenDART 회사 고유번호](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018)
- [OpenDART 원문 파일](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003)
- [OpenAI 구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)

[수집 코드](../src/audit_data_lab/kyc_dart.py) · [문단 탐색](../src/audit_data_lab/kyc_passages.py) · [산출물](portfolio/artifacts/00-kyc/output-guide.md)
