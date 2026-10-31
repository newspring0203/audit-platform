# README 그림과 실행 근거

| 자료 | 생성 근거 | 범위 |
|---|---|---|
| SAP 결과 PNG | 사용자가 제공한 실제 실행 화면 | 회사 3000·2007년 학습 예제 결과. 고객 감사 실적을 뜻하지 않는다. |
| QuickBooks 전후 PNG | 기존 합성 예제의 입력·결과 표 렌더링 | 웹 화면 캡처가 아니다. |
| 자금·조회 회신 SVG와 CSV | `scripts/build_portfolio_evidence.py`가 현재 Python 분석 함수를 호출하여 생성 | 합성 입력. 실제 고객·금융기관 회신이 아니다. |
| run_manifest.json | 실행 시점·조건·요약·입력 및 소스 해시 | 해당 실행의 재현 정보를 제공한다. |

저장소 루트에서 `.venv/bin/python scripts/build_portfolio_evidence.py`로 자금·조회 회신 근거를 재생성한다. 표의 공란과 대시는 비교 불가·미확보를 의미하며 0으로 해석하지 않는다.
