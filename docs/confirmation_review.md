# 조회 회신 검토

이미 확보한 회신을 CSV/XLSX 정리표로 입력받아 장부와 비교한다.  항목별 회신 원본·진위·전사 정확성과 미회신 후속 절차는 별도 확인한다.

## 실행

서버 재시작·브라우저 새로고침 후 감사 분석의 매출채권 조회 회신 / 금융기관 조회 회신 메뉴를 선택한다. 조회 기준일은 합성 예제의 경우 2026-10-31, 금액 허용 차이는 0이다. 작업 생성 후 ledger·requests·replies에 data/demo/confirmations의 AR 또는 BANK 세 파일을 각각 올린다. 두 시나리오는 별도 작업으로 실행한다. 결과와 검토 기록, 조서 ZIP은 기존 공통 화면에서 제공한다.

## 입력

- ledger: 단위·거래처(또는 금융기관·계좌·항목유형)·통화·기준일별 Balance. 동일 키는 한 행만 허용한다. 거래처 잔액은 사전 집계한 자료다.
- requests: Request_ID와 조회 대상 키. ID는 실제 발송번호 대신 항목별 내부 식별자다. 하나의 금융기관 원본 회신에 여러 계좌/차입 항목이 있으면 정리표에서 항목별 ID를 부여한다.
- replies: Request_ID, 조회 대상 키(As_Of_Date 대신 Reply_As_Of_Date), Response_Status, Confirmed_Balance, Evidence_Reference. 증빙 참조는 원문 파일명·문서번호·페이지 등이다. 상태는 confirmed(전액 회신), disputed(이의), partial(일부), unable(확인 불가)이다. 미회신은 요청 목록과 회신 목록의 연결 상태로 표시한다. 전부 미회신이면 헤더만 있는 회신 CSV를 제출한다. 중복 회신은 최종 회신 선택 근거를 정리한 후 한 건만 제출한다.
- 금융기관 ledger/replies의 Interest_Rate, Maturity_Date, Collateral, Guarantees, Restrictions, Other_Arrangements는 선택 열이다. 조건 값은 문자열로 비교하므로 금리 표기 차이도 검토 대상이다. 공란은 미확보 항목으로 표시한다.

## 결과

confirmation_comparison: 장부·요청·회신을 연결한 표. 동일 단위·대상·통화·기준일의 confirmed 회신만 장부-회신 금액 차이를 계산한다. matched는 정확한 금액 일치 상태다. within_tolerance는 비영(0이 아닌) 차이로 검토 목록에 남긴다. difference, no_reply, not_requested, ledger_missing, scope_mismatch, date_mismatch, partial, disputed, unable를 구분한다. 비교 불가 차이는 공란으로 표시한다.

review_items: 정확한 잔액 일치 외의 비교 항목. unlinked_replies: 요청 ID와 연결되지 않은 회신 원본 행. terms_review: 금융기관의 조건별 원문 대조 자료. 문자열이 같아도 미검토이며 금액 일치와 조건 검토 완료는 별개다. 각 결과의 확인 버튼은 장부·요청·회신 원본 행으로 연결한다. 담보·보증과 계좌 범위는 원문 검토에 연결한다.

## 합성 시연 예상

AR: 장부 6항목, 요청 5항목, 회신 4항목. 정확 일치·100 차이·미회신·일부 회신·기준일 차이·미요청 각 1항목. BANK: 장부/요청 3항목, 회신 2항목. 정확 일치 1, 차이 -1000 1, 미회신 1. 조건 12행 중 BANK2 담보는 문자열 차이가 있다. 예제 문서 참조는 합성 식별자다.

## Python

confirmations.ar_confirmation_review / bank_confirmation_review. 공통 review_confirmations에서 키·중복·날짜·금액을 검증한다. 웹은 analysis_dispatch.confirmation에서 호출한다. 입력은 장부·요청·회신 정리표와 분석 조건이다.
