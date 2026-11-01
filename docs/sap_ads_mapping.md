# SAP–ADS GL 변환 초안

참고 문서: **AICPA ADS — General Ledger Standard (July 2015)**.

| ADS 필드 | SAP 입력 | 처리 |
|---|---|---|
| Journal_ID | BUKRS/GJAHR/BELNR | 콜론으로 연결; 원본 문자열 유지 |
| Journal_ID_Line_Number | BUZEI | 문자열 유지 |
| JE_Header_Description | BKPF BKTXT | 이름 정확히 맞춤 |
| JE_Line_Description | BSEG SGTXT | 원문 유지 |
| Source | BLART | 임시 대응; 출처 목록 확인 필요 |
| Business_Unit_Code | BUKRS/GSBER | 임시 감사 단위; 회사별 확인 필요 |
| Effective_Date | BKPF BUDAT | YYYYMMDD |
| Fiscal_Year | GJAHR | 문자열 |
| Period | MONAT | 01~16; 회계 달력 확인 |
| GL_Account_Number | HKONT | 문자열 유지 |
| Amount | DMBTR | 소수 2자리; 음수 금액은 유지 |
| Amount_Credit_Debit_Indicator | SHKZG | S→D, H→C |
| Amount_Currency | HWAER | 기능통화 해석 확인 필요 |
| Entered_By | USNAM | 공란은 누락 보고서에 기록 |
| Entered_Date | CPUDT | YYYYMMDD |
| Entered_Time | CPUTM | HHMM, 원본 초는 보조 CSV에 보관 |
| Reversal_Indicator | 미매핑 | 확보·코드 의미 확인 필요 |

## TB

회사·연도·원장·실적구분·버전으로 먼저 선택합니다. HSLVT를 기초로 HSL01~16을 누적합니다. HSL의 통화 기준은 원본 시스템 설정과 대조합니다. 금액은 원본 부호를 유지해 누적합니다.

기간별 Amount_Beginning/Amount_Ending, Balance_AsOf_Date와 Amount_Currency를 생성합니다. 특별기간 13~16은 별도 행으로 남깁니다. 회계기간 처리는 달력연도 기준입니다.

## 결과 해석

생성 파일은 draft 상태로 제공하고 검증 차이를 결과표에 기록합니다. 계정과목표·출처 목록, 원본 추출 범위, 기능통화 및 감사 단위 확인이 필요합니다. 계정의 의미는 원본 계정과목표를 기준으로 확인합니다.

## 결합키와 원본 추적

현재 BSEG→BKPF 결합키는 `BUKRS + GJAHR + BELNR`이며 상세 식별에는 BUZEI가 추가됩니다. 추출은 단일 SAP 클라이언트 범위를 확인해 준비합니다. 헤더·상세 중복과 헤더 미연결을 검사하고 `validate='many_to_one'` 및 결합 전후 행 수로 중복 증식을 방지합니다.

BKPF에서 업무상 선택하는 필드는 연결키 3개와 BKTXT·BLART·BUDAT·BLDAT·CPUDT·CPUTM·MONAT·USNAM·HWAER의 총 12개입니다. `__source_row`는 프로그램이 추가하는 추적 필드입니다.

출력 `sap_lineage`는 GL 전표·행과 BSEG/BKPF 원본 행을 연결합니다. `gl_tb_reconciliation`은 계정·사업단위·연도·기간별 GL 순변동과 TB 거래금액을 비교합니다. 추출 범위는 원본 명세와 함께 확인합니다. [실제 코드](../src/audit_data_lab/sap.py)
