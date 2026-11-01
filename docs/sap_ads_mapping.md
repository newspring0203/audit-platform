# SAP–ADS GL 변환 초안

기준: AICPA ADS General Ledger July 2015. 전체 준수 검증은 완료되지 않았습니다.

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

회사·연도·원장·실적구분·버전으로 먼저 선택합니다. HSLVT를 기초로 HSL01~16을 누적합니다. HSL의 통화 의미는 원본 시스템 설정으로 확인해야 하며, 이를 확인하기 전에는 확정된 ADS 결과로 사용하지 않습니다. 원본 부호를 유지하며 차대변 구분으로 이중 부호 적용하지 않습니다.

기간별 Amount_Beginning/Amount_Ending, Balance_AsOf_Date와 Amount_Currency를 생성합니다. 특별기간 13~16은 별도 행으로 남깁니다. 달력연도를 가정하므로 비달력 회계연도는 지원하지 않습니다.

## 결과 해석

생성 파일에는 draft를 표시합니다. 검증 차이가 있어도 숨기지 않고 outputs/validation에 저장합니다. 계정과목표·출처 목록, 원본 추출 범위, 기능통화 및 감사 단위 확인이 필요합니다. 현금·매출 등 계정 의미는 원본 계정과목표 없이 추정하지 않습니다.

## 결합키와 원본 추적

현재 BSEG→BKPF 결합키는 `BUKRS + GJAHR + BELNR`이며 상세 식별에는 BUZEI가 추가됩니다. MANDT는 결합키에 포함되지 않아 여러 클라이언트가 섞이지 않았는지 추출 범위를 확인해야 합니다. 헤더·상세 중복과 헤더 미연결을 검사하고 `validate='many_to_one'` 및 결합 전후 행 수로 중복 증식을 방지합니다.

BKPF에서 업무상 선택하는 필드는 연결키 3개와 BKTXT·BLART·BUDAT·BLDAT·CPUDT·CPUTM·MONAT·USNAM·HWAER의 총 12개입니다. `__source_row`는 프로그램이 추가하는 추적 필드입니다. 원본의 전체 SAP 필드를 모두 출력하는 변환이 아닙니다.

출력 `sap_lineage`는 GL 전표·행과 BSEG/BKPF 원본 행을 연결합니다. `gl_tb_reconciliation`은 계정·사업단위·연도·기간별 GL 순변동과 TB 거래금액을 비교합니다. 두 자료가 일치해도 동일하게 누락된 범위를 발견했다는 뜻은 아닙니다. [실제 코드](../src/audit_data_lab/sap.py)
