"""명시된 TB 시점·분류·부호 정의로만 계산하는 잔액 비교·재무 지표 초안."""
import pandas as pd
from .common import columns,fail,money,text


def review_tb(tb,mapping,*,current_year,prior_year,period,sign_basis):
    columns(tb,['GL_Account_Number','Business_Unit_Code','Fiscal_Year','Period','Amount_Currency','Amount_Ending'],'TB')
    if period is None:fail('TB_PERIOD_REQUIRED','Period','비교할 TB 회계기간을 직접 지정하세요. 최신 잔액을 임의 선택하지 않습니다.',table='TB')
    period=str(period).zfill(2)
    if period not in [f'{n:02d}' for n in range(1,17)]:fail('INVALID_PERIOD','Period','TB 기간은 1~16이어야 합니다.',table='TB')
    t=tb.copy().reset_index(drop=True)
    for c in ['GL_Account_Number','Business_Unit_Code','Fiscal_Year','Period','Amount_Currency']:t[c]=text(t,c,'TB')
    t['Period']=t['Period'].str.zfill(2)
    t=t.loc[t['Fiscal_Year'].isin([str(current_year),str(prior_year)])&t['Period'].eq(period)].copy()
    if t.empty:fail('TB_SCOPE_EMPTY','Period','선택한 연도·기간의 시산표가 없습니다.',table='TB')
    if not t['Amount_Currency'].str.fullmatch(r'[A-Z]{3}').all():fail('INVALID_CURRENCY','Amount_Currency','TB 통화를 확인하세요.',table='TB')
    keys=['Business_Unit_Code','GL_Account_Number','Amount_Currency']
    if t.duplicated(keys+['Fiscal_Year']).any():fail('DUPLICATE_TB_KEY','GL_Account_Number','선택 범위에 시산표 계정 키가 중복됩니다. 원장·사업단위를 확인하세요.',table='TB')
    t['Ending_Cents']=money(t['Amount_Ending'],'Amount_Ending','TB')
    a=t.loc[t.Fiscal_Year.eq(str(current_year)),keys+['Ending_Cents']].rename(columns={'Ending_Cents':'Current_Cents'})
    b=t.loc[t.Fiscal_Year.eq(str(prior_year)),keys+['Ending_Cents']].rename(columns={'Ending_Cents':'Prior_Cents'})
    comparison=a.merge(b,on=keys,how='outer',indicator=True)
    comparison['Presence']=comparison.pop('_merge').astype('string')
    comparison['Current_Balance']=comparison['Current_Cents']/100;comparison['Prior_Balance']=comparison['Prior_Cents']/100
    comparison['Balance_Change']=(comparison['Current_Cents']-comparison['Prior_Cents'])/100
    comparison['Balance_Change_Pct']=(comparison['Current_Cents']-comparison['Prior_Cents'])/comparison['Prior_Cents'].abs().where(comparison['Prior_Cents'].ne(0))*100
    ratio_columns=['Business_Unit_Code','Fiscal_Year','Amount_Currency','Metric','Value','Unit','Status','Reason']
    issues=[]
    if mapping is None or sign_basis!='debit_positive':
        issues.append({'code':'RATIO_BASIS_MISSING','field':'Account_Mapping','message':'계정 분류표와 차변 양수·대변 음수의 TB 부호 정의가 필요합니다.','source_file':'TB','suggested_review':'계정별 Metric_Group·Sign_Multiplier와 TB 부호 기준을 확인하세요.'})
        return comparison,pd.DataFrame(columns=ratio_columns),pd.DataFrame(),issues,'basis_information_missing'
    columns(mapping,['Business_Unit_Code','GL_Account_Number','Metric_Group','Sign_Multiplier'],'Account_Mapping')
    m=mapping.copy()
    for c in ['Business_Unit_Code','GL_Account_Number','Metric_Group']:m[c]=text(m,c,'Account_Mapping')
    if m.duplicated(['Business_Unit_Code','GL_Account_Number']).any():fail('DUPLICATE_ACCOUNT_MAPPING','GL_Account_Number','계정 분류가 중복됩니다.',table='Account_Mapping')
    m['Sign_Multiplier']=pd.to_numeric(m['Sign_Multiplier'],errors='coerce')
    if not m['Sign_Multiplier'].isin([-1,1]).all():fail('INVALID_SIGN_MAPPING','Sign_Multiplier','계정별 부호 배수는 +1 또는 -1이어야 합니다.',table='Account_Mapping')
    groups={'current_assets','noncurrent_assets','current_liabilities','noncurrent_liabilities','equity','other'}
    if not m['Metric_Group'].isin(groups).all():fail('INVALID_METRIC_GROUP','Metric_Group','지원하는 재무 지표 계정 분류를 사용하세요.',table='Account_Mapping')
    joined=t.merge(m,on=['Business_Unit_Code','GL_Account_Number'],how='left',validate='many_to_one',indicator=True)
    joined['Metric_Cents']=joined['Ending_Cents']*joined['Sign_Multiplier']
    ratios=[];components=[]
    for (unit,year,currency),part in joined.groupby(['Business_Unit_Code','Fiscal_Year','Amount_Currency']):
        values=part.groupby('Metric_Group')['Metric_Cents'].sum().to_dict()
        unmapped=part['_merge'].ne('both').any()
        for group,value in values.items():components.append({'Business_Unit_Code':unit,'Fiscal_Year':year,'Amount_Currency':currency,'Metric_Group':group,'Amount':value/100})
        for name,needed,unit_label in [('Current_Ratio',{'current_assets','current_liabilities'},'times'),
                ('Working_Capital',{'current_assets','current_liabilities'},currency),
                ('Debt_To_Equity',{'current_liabilities','noncurrent_liabilities','equity'},'times')]:
            value=None;status='calculated_draft';reason='사용자 제공 분류·부호 정의에 따른 산술 계산'
            if unmapped:status='not_executed';reason='선택 TB에 미분류 계정이 있음'
            elif not needed<=set(values):status='not_executed';reason='필요한 계정 그룹이 누락됨. 0으로 추정하지 않음'
            elif name=='Working_Capital':value=(values['current_assets']-values['current_liabilities'])/100
            else:
                denominator=values['current_liabilities'] if name=='Current_Ratio' else values['equity']
                if denominator<=0:status='not_executed';reason='분모가 0 또는 음수여서 지표 해석을 확인해야 함'
                else:value=values['current_assets']/denominator if name=='Current_Ratio' else (values['current_liabilities']+values['noncurrent_liabilities'])/denominator
            ratios.append({'Business_Unit_Code':unit,'Fiscal_Year':year,'Amount_Currency':currency,'Metric':name,'Value':value,'Unit':unit_label,'Status':status,'Reason':reason})
    ratios=pd.DataFrame(ratios,columns=ratio_columns)
    if joined['_merge'].ne('both').any():issues.append({'code':'UNMAPPED_TB_ACCOUNT','field':'GL_Account_Number','message':'미분류 TB 계정이 있는 단위·통화의 지표는 계산하지 않았습니다.','source_file':'Account_Mapping','suggested_review':'계정과목표의 누락 분류와 반대 성격 계정 부호를 확인하세요.'})
    status='calculated_draft' if ratios['Status'].eq('calculated_draft').all() else 'partially_not_executed'
    return comparison,ratios,pd.DataFrame(components),issues,status
