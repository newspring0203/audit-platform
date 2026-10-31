"""화면과 API가 공유하는 입력 조건 설명. 분석 기준을 자동 승인하지 않는다."""
from datetime import date
import re
from .storage import ServiceError

def field(key,label,kind='text',default='',**extra):return {'key':key,'label':label,'kind':kind,'default':default,**extra}

def module_ui():
    today=date.today();year=str(today.year)
    return {
      'ar_confirmation':{'description':'거래처별 장부 잔액과 이미 확보한 조회 회신 정리표를 비교한다. 미회신·일부 회신·기준일 차이를 구분한다.','fields':[field('as_of','조회 기준일','date',today.isoformat(),required=True),field('amount_tolerance','금액 허용 차이 (통화 단위)','decimal',0,min=0,max=1000000000)]},
      'bank_confirmation':{'description':'금융기관 항목별 잔액과 회신을 비교하고 금리·만기·담보·보증 등을 원문 검토 대상으로 표시한다. 조회서 발송·진위 확인은 별도다.','fields':[field('as_of','조회 기준일','date',today.isoformat(),required=True),field('amount_tolerance','금액 허용 차이 (통화 단위)','decimal',0,min=0,max=1000000000)]},
      'sap_preprocessing':{'description':'SAP 상세(BSEG)·헤더(BKPF)·계정잔액(GLT0)을 결합해 GL·TB를 생성하고 전표 차대와 GL–TB 기간별 움직임을 대사합니다. 달력연도·소수 2자리 기준이며 통화와 추출 범위 확인이 필요합니다.','fields':[field('company','회사코드',required=True),field('fiscal_year','회계연도','year',required=True),field('ledger','원장',default='0',required=True),field('record_type','실적구분',default='0',required=True),field('version','버전',default='1',required=True)]},
      'jet':{'description':'전표의 이상 징후와 선정 이유를 확인합니다. 별도 거래 기록과의 대사는 금액·통화·범위의 근거 확인이 필요합니다.','fields':[field('company','회사코드 (기존 SAP 로그 변환 시)'),field('fiscal_year','회계연도 (기존 SAP 로그 변환 시)','year'),field('round_unit','정액 거래 기준 단위','number',1000,min=1,max=1000000000),field('rare_user_max','저빈도 사용자 최대 행 수','number',10,min=0,max=1000000000),field('rare_account_max','저빈도 계정 최대 행 수','number',3,min=0,max=1000000000),field('combined_rule_min','복합 조건 최소 규칙 수','number',2,min=2,max=100)]},
      'analytical_review':{'description':'GL 전기·당기 순변동과 월별 차이를 비교합니다. TB 재무비율은 계정 분류와 부호 기준 확인이 추가로 필요합니다.','fields':[field('current_year','당기 연도','year',year,required=True),field('prior_year','전기 연도','year',str(today.year-1),required=True),field('change_threshold_pct','검토 증감률 (%)','decimal',30,min=0,max=1000000000),field('tb_period','TB 비교 회계기간 (GL 필터 아님)','select','',options=[['','TB 미사용 / 기간 미지정']]+[[str(i).zfill(2),str(i)] for i in range(1,17)]),field('tb_sign_basis','TB 부호 기준 확인','select','',options=[['','미확인 — 재무비율 계산 안 함'],['debit_positive','자료가 차변 양수·대변 음수임을 확인함']])]},
      'cash_proofing':{'description':'계좌·통화·부호 금액 및 설정 시차의 상호 유일 후보를 연결합니다. 미대사만으로 통제 미비를 확정하지 않습니다.','fields':[field('as_of','분석 기준일','date',today.isoformat()),field('date_tolerance_days','허용 일자 차이 (일)','number',0,min=0,max=365),field('aging_days','장기 미대사 기준 (일)','number',30,min=0,max=3650)]},
      'inventory':{'description':'기초·입출고 수량을 검토합니다. 로트 연령은 기말 수량이 대사되는 로트 명세가 있어야 계산합니다.','fields':[field('as_of','재고 기준일','date',today.isoformat(),required=True),field('stale_days','장기 미출고 기준 (일)','number',180,min=0,max=36500)]},
      'data_cleansing':{'description':'누락·중복·날짜·금액 오류를 확인하고, 지정한 매핑표로 컬럼명을 정리합니다.','fields':[field('required_columns','필수 컬럼 (쉼표로 구분)','list'),field('date_columns','날짜 검사 컬럼 (쉼표로 구분)','list'),field('amount_columns','금액 검사 컬럼 (쉼표로 구분)','list')]},
      'kyc':{'description':'사용자가 지정한 회사를 OpenDART에서 조회합니다. 실제 호출 검증은 별도이며 AI는 서버에서 허용한 경우에만 사용할 수 있습니다.','fields':[field('company','회사명 또는 DART 고유번호',required=True),field('start_date','조회 시작일','date',f'{year}-01-01',required=True),field('end_date','조회 종료일','date',today.isoformat(),required=True),field('report_type','보고서 종류','select','A001',options=[['A001','사업보고서'],['A002','반기보고서'],['A003','분기보고서']]),field('max_reports','최대 수집 보고서','number',1,min=1,max=5),field('with_ai','AI 요약 사용 (서버 허용 필요)','checkbox',False)]},
      'gl_user_split':{'description':'입력 사용자별 GL 행을 나눕니다. 여러 사용자 행이 있는 전표는 파일들로 나뉠 수 있습니다.','fields':[field('user_column','입력 사용자 컬럼',default='Entered_By',required=True),field('max_groups','최대 분할 파일 수','number',500,min=1,max=2000)]},
      'quickbooks_preprocessing':{'description':'QuickBooks 계정별 보고서를 거래 표로 정리합니다. 지원 형식과 ADS 변환 전 확인사항은 아래에서 확인하세요.','fields':[field('date_format','원본 문자열 날짜 형식','select','%Y-%m-%d',options=[['%Y-%m-%d','2026-10-31 (연-월-일)'],['%m/%d/%Y','10/31/2026 (월/일/연도)'],['%d/%m/%Y','31/10/2026 (일/월/연도)'],['%Y%m%d','20261031 (연월일)']])]}}

GL=['Journal_ID','GL_Account_Number','Business_Unit_Code','Fiscal_Year','Period','Amount','Amount_Currency','Amount_Credit_Debit_Indicator','Effective_Date','Entered_Date','Entered_By']
TEMPLATES={
 'sap_preprocessing':{},
 'jet':{'gl':GL,'log':['Journal_ID','Total','Amount_Currency','Amount_Credit_Debit_Indicator']},
 'analytical_review':{'gl':GL,'tb':['GL_Account_Number','Business_Unit_Code','Fiscal_Year','Period','Amount_Currency','Amount_Ending'],'account_mapping':['Business_Unit_Code','GL_Account_Number','Metric_Group','Sign_Multiplier']},
 'cash_proofing':{slot:['Row_ID','Bank_Account','Currency','Date','Amount'] for slot in ['bank','cash_gl']},
 'inventory':{'movements':['Item_ID','Date','Quantity_In','Quantity_Out'],'opening':['Item_ID','Opening_Quantity'],'lot_snapshot':['Item_ID','Lot_ID','Receipt_Date','Snapshot_Date','Remaining_Quantity']},
 'data_cleansing':{'data':[],'mapping':['Target_Field','Source_Field']},'kyc':{},
 'gl_user_split':{'gl':['Journal_ID','Entered_By','Amount']},
 'quickbooks_preprocessing':{'quickbooks':['','','','','','Type','Date','Num','Name','Memo','Split','Amount','Balance']}}
TEMPLATES['cash_proofing']['balances']=['Bank_Account','Currency','As_Of_Date','Bank_Balance','GL_Balance','Bank_Adjustment','Adjustment_Reference']

def validate_parameters(module,parameters):
    definitions={f['key']:f for f in module_ui()[module]['fields']}
    for key,value in parameters.items():
        f=definitions[key];kind=f['kind'];ok=True
        if value is None:ok=False
        elif kind in {'number','decimal'}:ok=not isinstance(value,bool) and isinstance(value,(int,float)) and f['min']<=value<=f['max'] and (kind=='decimal' or int(value)==value)
        elif kind=='year':ok=not isinstance(value,bool) and bool(re.fullmatch(r'\d{4}',str(value)))
        elif kind=='date':
            try:__import__('datetime').datetime.strptime(value,'%Y%m%d')
            except (ValueError,TypeError):ok=False
        elif kind=='select':ok=value in [option[0] for option in f['options'] if option[0]]
        elif kind=='checkbox':ok=isinstance(value,bool)
        elif kind=='list':ok=isinstance(value,list) and all(isinstance(v,str) and v.strip() for v in value)
        else:ok=isinstance(value,str) and bool(value.strip())
        if not ok:raise ServiceError('INVALID_PARAMETERS',f"{f['label']}의 형식 또는 범위를 확인하세요.",422)
    if parameters.get('current_year') is not None and str(parameters['current_year'])==str(parameters.get('prior_year')):raise ServiceError('INVALID_PARAMETERS','전기·당기는 서로 다른 연도를 지정하세요.',422)
    if parameters.get('start_date','')>parameters.get('end_date','99999999'):raise ServiceError('INVALID_PARAMETERS','조회 시작일과 종료일 순서를 확인하세요.',422)

TEMPLATES['sap_preprocessing']={'bseg': ['BUKRS (Company Code)', 'GJAHR (Fiscal Year)', 'BELNR (Accounting Document Number)', 'GSBER (Business Area)', 'SGTXT (Item Text)', 'BUZEI (Number of Line Item Within Accounting Document)', 'HKONT (General Ledger Account)', 'DMBTR (Amount in Local Currency)', 'SHKZG (Debit/Credit Indicator)'], 'bkpf': ['BUKRS (Company Code)', 'GJAHR (Fiscal Year)', 'BELNR (Accounting Document Number)', 'BKTXT (Document Header Text)', 'BLART (Document Type)', 'BUDAT (Posting Date in the Document)', 'BLDAT (Document Date in Document)', 'CPUDT (Day On Which Accounting Document Was Entered)', 'CPUTM (Time of Entry)', 'MONAT (Fiscal Period)', 'USNAM (User name)', 'HWAER (Local Currency)'], 'glt0': ['BUKRS (Company Code)', 'RYEAR (Fiscal Year)', 'RLDNR (Ledger)', 'RRCTY (Record Type)', 'RVERS (Version)', 'RACCT (Account Number)', 'RBUSA (Business Area)', 'HSLVT (Balance carried forward in local currency (currency 2))', 'HSL01 (Total transactions in the period in local currency (curr 2))', 'HSL02 (Total transactions in the period in local currency (curr 2))', 'HSL03 (Total transactions in the period in local currency (curr 2))', 'HSL04 (Total transactions in the period in local currency (curr 2))', 'HSL05 (Total transactions in the period in local currency (curr 2))', 'HSL06 (Total transactions in the period in local currency (curr 2))', 'HSL07 (Total transactions in the period in local currency (curr 2))', 'HSL08 (Total transactions in the period in local currency (curr 2))', 'HSL09 (Total transactions in the period in local currency (curr 2))', 'HSL10 (Total transactions in the period in local currency (curr 2))', 'HSL11 (Total transactions in the period in local currency (curr 2))', 'HSL12 (Total transactions in the period in local currency (curr 2))', 'HSL13 (Total transactions in the period in local currency (curr 2))', 'HSL14 (Total transactions in the period in local currency (curr 2))', 'HSL15 (Total transactions in the period in local currency (curr 2))', 'HSL16 (Total transactions in the period in local currency (curr 2))']}

from audit_data_lab.confirmations import AR_KEYS,BANK_KEYS,TERMS
for _module,_keys in [('ar_confirmation',AR_KEYS),('bank_confirmation',BANK_KEYS)]:
    TEMPLATES[_module]={'ledger':[*_keys,'Balance'],'requests':['Request_ID',*_keys],'replies':['Request_ID',*_keys[:-1],'Response_Status','Reply_As_Of_Date','Confirmed_Balance','Evidence_Reference']}
    if _module=='bank_confirmation':
        TEMPLATES[_module]['ledger']+=TERMS
        TEMPLATES[_module]['replies']+=TERMS
