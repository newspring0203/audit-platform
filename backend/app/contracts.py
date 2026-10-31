"""각 분석 페이지의 허용 입력과 조건. 사용자·회사 소유권은 본문에서 받지 않는다."""
from pydantic import BaseModel,ConfigDict,Field,field_validator
from typing import Any,Literal
import math
from .storage import ServiceError
from .ui_schema import validate_parameters

MODULES={
 'ar_confirmation':{'inputs':['ledger','requests','replies'],'parameters':{'as_of','amount_tolerance'}},
 'bank_confirmation':{'inputs':['ledger','requests','replies'],'parameters':{'as_of','amount_tolerance'}},
 'sap_preprocessing':{'inputs':['bseg','bkpf','glt0'],'parameters':{'company','fiscal_year','ledger','record_type','version'}},
 'quickbooks_preprocessing':{'inputs':['quickbooks'],'parameters':{'date_format'}},
 'gl_user_split':{'inputs':['gl'],'parameters':{'user_column','max_groups'}},
 'jet':{'inputs':['gl','log'],'parameters':{'company','fiscal_year','round_unit','rare_user_max','rare_account_max','combined_rule_min'}},
 'analytical_review':{'inputs':['gl','tb','account_mapping'],'parameters':{'current_year','prior_year','change_threshold_pct','tb_period','tb_sign_basis'}},
 'cash_proofing':{'inputs':['bank','cash_gl','balances'],'parameters':{'date_tolerance_days','as_of','aging_days'}},
 'inventory':{'inputs':['movements','opening','lot_snapshot'],'parameters':{'as_of','stale_days'}},
 'data_cleansing':{'inputs':['data','mapping'],'parameters':{'required_columns','date_columns','amount_columns'}},
 'kyc':{'inputs':[],'parameters':{'company','start_date','end_date','max_reports','with_ai','report_type'}},
}

REQUIRED_INPUTS={'ar_confirmation':['ledger','requests','replies'],'bank_confirmation':['ledger','requests','replies'],'sap_preprocessing':['bseg','bkpf','glt0'],'quickbooks_preprocessing':['quickbooks'],'gl_user_split':['gl'],'jet':['gl','log'],'analytical_review':['gl'],'cash_proofing':['bank','cash_gl'],'inventory':['movements','opening'],'data_cleansing':['data'],'kyc':[]}
for name,config in MODULES.items():
    config['required_inputs']=REQUIRED_INPUTS[name]
    config['optional_inputs']=[slot for slot in config['inputs'] if slot not in REQUIRED_INPUTS[name]]

class NewJob(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    module:Literal['ar_confirmation','bank_confirmation','sap_preprocessing','quickbooks_preprocessing','gl_user_split','jet','analytical_review','cash_proofing','inventory','data_cleansing','kyc']
    parameters:dict[str,Any]=Field(default_factory=dict,max_length=16)

    @field_validator('parameters')
    @classmethod
    def simple_parameters(cls,value):
        for key,item in value.items():
            if len(key)>64:raise ValueError('조건 이름이 너무 깁니다.')
            if isinstance(item,str):
                if len(item)>200:raise ValueError('조건 값이 너무 깁니다.')
            elif isinstance(item,list):
                if len(item)>64 or any(not isinstance(x,str) or len(x)>128 for x in item):raise ValueError('컬럼 조건을 확인하세요.')
            elif isinstance(item,float) and not math.isfinite(item):raise ValueError('유한한 숫자만 허용합니다.')
            elif not isinstance(item,(int,float,bool,type(None))):raise ValueError('지원하지 않는 조건 형식입니다.')
            if key=='with_ai' and not isinstance(item,bool):raise ValueError('with_ai는 true 또는 false여야 합니다.')
            if key in {'required_columns','date_columns','amount_columns'} and not isinstance(item,list):raise ValueError('컬럼 조건은 목록이어야 합니다.')
        return value

    def checked(self):
        if set(self.parameters)-MODULES[self.module]['parameters']:
            raise ServiceError('INVALID_PARAMETERS','이 기능에서 허용하지 않는 조건입니다.',422)
        validate_parameters(self.module,self.parameters)
        return self
