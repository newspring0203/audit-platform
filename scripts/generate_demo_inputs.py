"""제출 시연용 합성 입력 생성. 실제 고객 자료를 읽지 않는다."""
from pathlib import Path
from decimal import Decimal
import json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

def generate():
    out=ROOT/'data'/'demo'/'v1';out.mkdir(parents=True,exist_ok=True)
    frames={}
    def save(name,rows):
        frame=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
        frame.to_csv(out/name,index=False,encoding='utf-8-sig');frames[name]=frame
        return frame
    gl=[]
    def journal(year,n,month,day,amount,user,time='1000'):
        for line,account,dc in [('001','1000','D'),('002','4000','C')]:
            gl.append({'Journal_ID':f'DEMO:{year}:J{n:03d}','Journal_ID_Line_Number':line,'GL_Account_Number':account,'Business_Unit_Code':'DEMO:HQ','Fiscal_Year':str(year),'Period':f'{month:02d}','Amount':str(amount),'Amount_Currency':'KRW','Amount_Credit_Debit_Indicator':dc,'Effective_Date':f'{year}{month:02d}{day:02d}','Entered_Date':f'{year}{month:02d}{day:02d}','Entered_Time':time,'Entered_By':user,'Source':'DEMO_MANUAL','JE_Line_Description':'합성 시연 거래','JE_Header_Description':'SYNTHETIC DEMO'})
    for year,amounts in [(2025,[1000,2000]),(2026,[2000,5000])]:
        for n,(month,amount) in enumerate(zip([9,10],amounts),1):journal(year,n,month,15,amount,'DEMO_A' if n==1 else 'DEMO_B')
    compare=save('gl_comparison.csv',gl)
    gl=compare.loc[compare.Fiscal_Year.eq('2026')].to_dict('records');journal(2026,3,10,31,3000,'DEMO_RARE','2315')
    jet=save('gl_jet.csv',gl)
    log=jet.groupby(['Journal_ID','Amount_Currency','Amount_Credit_Debit_Indicator'],sort=False)['Amount'].agg(lambda v:str(sum(Decimal(str(x)) for x in v))).reset_index(name='Total');save('log_control.csv',log)
    tb=[];mapping=[]
    specs=[('1000','current_assets',1,[20000,35000]),('1500','noncurrent_assets',1,[5000,5000]),('2000','current_liabilities',-1,[-5000,-7000]),('2500','noncurrent_liabilities',-1,[-2000,-4000]),('3000','equity',-1,[-18000,-29000])]
    for account,group,sign,amounts in specs:
        mapping.append({'Business_Unit_Code':'DEMO:HQ','GL_Account_Number':account,'Metric_Group':group,'Sign_Multiplier':sign})
        for year,amount in zip([2025,2026],amounts):tb.append({'Business_Unit_Code':'DEMO:HQ','GL_Account_Number':account,'Fiscal_Year':str(year),'Period':'10','Amount_Currency':'KRW','Amount_Ending':str(amount)})
    save('tb.csv',tb);save('account_mapping.csv',mapping)
    def transactions(prefix,items):return [{'Row_ID':prefix+str(i+1),'Bank_Account':'DEMO_BANK_01','Currency':'KRW','Date':date,'Amount':str(amount)} for i,(date,amount) in enumerate(items)]
    save('bank.csv',transactions('B',[('20261028',100000),('20261020',-5000),('20261025',7000),('20261026',3000),('20261026',3000)]))
    save('cash_gl.csv',transactions('G',[('20261029',100000),('20261020',-5000),('20261022',-9000),('20261026',3000)]))
    save('balances.csv',[{'Bank_Account':'DEMO_BANK_01','Currency':'KRW','As_Of_Date':'20261031','Bank_Balance':'112000','GL_Balance':'110000','Bank_Adjustment':'-2000','Adjustment_Reference':'DEMO_ADJ_01'}])
    save('opening.csv',[{'Item_ID':item,'Opening_Quantity':qty} for item,qty in [('DEMO_A',10),('DEMO_B',5),('DEMO_C',0)]])
    save('movements.csv',[{'Item_ID':item,'Date':date,'Quantity_In':qin,'Quantity_Out':qout} for item,date,qin,qout in [('DEMO_A','20261001',0,12),('DEMO_A','20261002',5,0),('DEMO_B','20260101',0,1),('DEMO_C','20261030',8,0)]])
    save('lot_snapshot.csv',[{'Item_ID':item,'Lot_ID':'LOT_'+item,'Receipt_Date':receipt,'Snapshot_Date':'20261031','Remaining_Quantity':qty} for item,receipt,qty in [('DEMO_A','20261002',3),('DEMO_B','20250101',4),('DEMO_C','20261030',8)]])
    raw=[{'전표번호':'DEMO01','계정번호':'1000','거래일자':'20261001','금액':'1000','입력자':'DEMO_A'}, {'전표번호':'DEMO02','계정번호':'4000','거래일자':'20260230','금액':'oops','입력자':'DEMO_B'}]
    raw+=[raw[1].copy(),{'전표번호':'DEMO03','계정번호':'','거래일자':'','금액':'200','입력자':''}]
    save('cleansing_raw.csv',raw)
    save('cleansing_mapping.csv',[{'Source_Field':s,'Target_Field':t} for s,t in [('전표번호','Journal_ID'),('계정번호','GL_Account_Number'),('거래일자','Effective_Date'),('금액','Amount'),('입력자','Entered_By')]])
    from audit_data_lab.quickbooks import REPORT_FIELDS
    qb=[[None]*5+REPORT_FIELDS]
    def qbrow(account=None,**values):
        return [account,None,None,None,None]+[values.get(field) for field in REPORT_FIELDS]
    qb += [qbrow('DEMO Cash'),qbrow(Type='Deposit',Date='2026-10-15',Num='0001',Name='DEMO Customer',Memo='Synthetic only',Split='DEMO Sales',Amount=5000,Balance=5000),qbrow('Total Cash',Amount=5000,Balance=5000),qbrow('DEMO Sales'),qbrow(Type='Invoice',Date='2026-10-15',Num='0001',Name='DEMO Customer',Amount=-5000,Balance=-5000)]
    pd.DataFrame(qb).to_csv(out/'quickbooks_report.csv',index=False,header=False,encoding='utf-8-sig')
    (out/'quickbooks_matrix.json').write_text(json.dumps(qb,ensure_ascii=False))
    # 예상값은 엔진을 실제 실행한 결과로 기록한다.
    from audit_data_lab import analytical_review,cash_proofing,inventory_analysis,cleanse_data,split_gl_by_user,run_jet
    read=lambda n:pd.read_csv(out/n,dtype='string',encoding='utf-8-sig')
    results={
      'analytical_review':analytical_review(read('gl_comparison.csv'),current_year='2026',prior_year='2025',tb=read('tb.csv'),account_mapping=read('account_mapping.csv'),tb_period='10',tb_sign_basis='debit_positive'),
      'jet':run_jet(read('gl_jet.csv'),read('log_control.csv')),
      'cash_proofing':cash_proofing(read('bank.csv'),read('cash_gl.csv'),date_tolerance_days=2,as_of='20261031',aging_days=5,balances=read('balances.csv')),
      'inventory':inventory_analysis(read('movements.csv'),read('opening.csv'),as_of='20261031',stale_days=180,lot_snapshot=read('lot_snapshot.csv')),
      'data_cleansing':cleanse_data(read('cleansing_raw.csv'),mapping=read('cleansing_mapping.csv'),required_columns=['GL_Account_Number','Effective_Date','Amount'],date_columns=['Effective_Date'],amount_columns=['Amount']),
      'gl_user_split':split_gl_by_user(read('gl_jet.csv'))}
    expected={name:r.summary for name,r in results.items()}
    (out/'expected_results.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2,allow_nan=False))
    manifest={name:{'rows':len(frame),'columns':list(frame.columns)} for name,frame in frames.items()}
    (out/'manifest.json').write_text(json.dumps({'source':'SYNTHETIC DEMO ONLY','files':manifest},ensure_ascii=False,indent=2))
    print(json.dumps(expected,ensure_ascii=False))
    return out

if __name__=='__main__':generate()
