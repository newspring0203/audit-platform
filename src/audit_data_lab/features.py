"""현재 구현 범위를 사용자 화면에서도 구분할 수 있는 기능 목록."""
FEATURES = [
 {'id':'ar_confirmation','name':'매출채권 조회 회신','status':'basic','entrypoint':'confirmations.ar_confirmation_review','needs':'장부·요청·회신 정리표'},
 {'id':'bank_confirmation','name':'금융기관 조회 회신','status':'basic','entrypoint':'confirmations.bank_confirmation_review','needs':'장부·요청·회신 정리표; 원문 검토 별도'},
 {'id':'sap_preprocessing','name':'SAP 전처리','status':'basic','entrypoint':'sap.convert_sap_data','needs':'BSEG·BKPF·GLT0 및 회사·연도·원장·실적구분·버전'},
 {'id':'quickbooks_preprocessing','name':'QuickBooks 보고서 전처리','status':'basic','entrypoint':'quickbooks.reshape_quickbooks_report','needs':'기존 예제 레이아웃 원본 Excel/CSV; ADS 변환은 별도'},
 {'id':'gl_user_split','name':'입력 사용자별 GL 분할','status':'basic','entrypoint':'gl_split.split_gl_by_user','needs':'전처리 GL 및 Entered_By; 미확보 사용자는 별도 파일'},
 {'id':'jet','name':'총계정원장 테스트','status':'basic','entrypoint':'jet.run_jet','needs':'ADS GL + 표준화 로그'},
 {'id':'analytical_review','name':'분석적 검토','status':'basic','entrypoint':'analytics.analytical_review','needs':'2개 연도 GL; 재무비율은 TB·계정 분류·부호 기준 추가 필요'},
 {'id':'working_paper','name':'감사 지원 조서','status':'basic','entrypoint':'working_papers.generate_working_paper','needs':'분석 결과; Markdown/CSV·설정 시 Excel 미검토 초안'},
 {'id':'kyc','name':'KYC','status':'credentials_required','entrypoint':'kyc_live.run_live_kyc','needs':'OpenDART 키; AI 사용 시 OpenAI 키·모델 추가'},
 {'id':'cash_proofing','name':'자금 대사','status':'basic','entrypoint':'cash.cash_proofing','needs':'계좌·통화·일자·부호를 맞춘 은행/GL 거래'},
 {'id':'inventory','name':'재고 수불 분석','status':'basic','entrypoint':'inventory.inventory_analysis','needs':'수불·기초 수량·기준일; 로트 연령은 검증 가능한 기말 로트 명세 추가'},
 {'id':'data_cleansing','name':'데이터 클렌징','status':'basic','entrypoint':'column_mapping.cleanse_data','needs':'원본 표·명시적 매핑표; 매핑 제안 자동 적용 안 함'},
]
