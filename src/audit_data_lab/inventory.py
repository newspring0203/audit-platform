"""수불·기초 수량으로 기말 수량 및 장기 미출고 후보를 계산한다."""
import numpy as np
import pandas as pd
from .common import AnalysisResult, columns, date_values, fail, text
from .validation import DataValidationError


def inventory_analysis(movements, opening, *, as_of, stale_days=180, lot_snapshot=None):
    if stale_days<0:raise ValueError('장기 미출고 기준은 0 이상이어야 합니다.')
    columns(movements,['Item_ID','Date','Quantity_In','Quantity_Out'],'Inventory')
    columns(opening,['Item_ID','Opening_Quantity'],'Opening')
    m=movements.copy().reset_index(drop=True);o=opening.copy().reset_index(drop=True)
    for f,table in [(m,'Inventory'),(o,'Opening')]:f['Item_ID']=text(f,'Item_ID',table)
    if o['Item_ID'].duplicated().any():fail('DUPLICATE_KEY','Item_ID','기초 수량의 품목이 중복됩니다.',table='Opening')
    if not set(m['Item_ID'])<=set(o['Item_ID']):fail('MISSING_OPENING','Item_ID','모든 수불 품목에 명시적 기초 수량이 필요합니다.',table='Opening')
    dates=date_values(m['Date'],'Date','Inventory')
    end=date_values(pd.Series([as_of]),'As_Of','Config').iloc[0]
    if dates.gt(end).any():fail('FUTURE_MOVEMENT','Date','기준일 이후 수불이 있습니다.',table='Inventory')
    for frame,fields,table in [(m,['Quantity_In','Quantity_Out'],'Inventory'),(o,['Opening_Quantity'],'Opening')]:
        for c in fields:
            values=pd.to_numeric(frame[c],errors='coerce')
            if (values.isna()|~np.isfinite(values.to_numpy(dtype=float,na_value=float('nan')))).any():
                fail('INVALID_QUANTITY',c,'수량은 유한한 숫자여야 합니다.',table=table)
            if c!='Opening_Quantity' and values.lt(0).any():fail('INVALID_QUANTITY',c,'입출고 수량은 0 이상이어야 합니다.',table=table)
            frame[c]=values
    m['_date']=dates
    totals=m.groupby('Item_ID')[['Quantity_In','Quantity_Out']].sum().reset_index()
    result=o.merge(totals,on='Item_ID',how='left',validate='one_to_one')
    result[['Quantity_In','Quantity_Out']]=result[['Quantity_In','Quantity_Out']].fillna(0)
    last_out=m.loc[m['Quantity_Out'].gt(0)].groupby('Item_ID')['_date'].max()
    result['Last_Out_Date']=result['Item_ID'].map(last_out)
    result['Days_Since_Last_Out']=(end-result['Last_Out_Date']).dt.days
    result['No_Outflow_In_Data']=result['Last_Out_Date'].isna()
    result['Ending_Quantity']=result['Opening_Quantity']+result['Quantity_In']-result['Quantity_Out']
    result['Negative_Stock']=result['Ending_Quantity'].lt(0)
    result['Stale_Candidate']=result['Ending_Quantity'].gt(0)&result['Days_Since_Last_Out'].ge(stale_days)
    result['Review_Required']=result['Negative_Stock']|result['Stale_Candidate']|(
        result['Ending_Quantity'].gt(0)&result['No_Outflow_In_Data'])
    # 기간 중 수량 흐름. 같은 날의 처리 순서는 원본 행 순서이며 실제 처리시각을 추정하지 않는다.
    m['Source_Row']=range(2,len(m)+2)
    m['Net_Quantity']=m['Quantity_In']-m['Quantity_Out']
    timeline=m.sort_values(['Item_ID','_date','Source_Row']).copy()
    starts=o.set_index('Item_ID')['Opening_Quantity']
    timeline['Running_Quantity']=timeline.groupby('Item_ID')['Net_Quantity'].cumsum()+timeline['Item_ID'].map(starts)
    negative_events=timeline.loc[timeline['Running_Quantity'].lt(0)].copy()
    negative_events['Review_Reason']='제출 순서 기준 계산 수량이 음수: 기초·누락·동일일자 순서 확인'
    monthly=m.assign(Period=m['_date'].dt.strftime('%Y-%m')).groupby(['Item_ID','Period'])[['Quantity_In','Quantity_Out']].sum().reset_index()
    monthly['Net_Quantity']=monthly['Quantity_In']-monthly['Quantity_Out']
    lot_aging=pd.DataFrame();lot_recon=pd.DataFrame();aging_buckets=pd.DataFrame();issues=[];lot_status='not_provided'
    if lot_snapshot is not None:
        try:
            columns(lot_snapshot,['Item_ID','Lot_ID','Receipt_Date','Snapshot_Date','Remaining_Quantity'],'Lots')
            lots=lot_snapshot.copy().reset_index(drop=True)
            for c in ['Item_ID','Lot_ID','Snapshot_Date']:lots[c]=text(lots,c,'Lots')
            if not lots['Snapshot_Date'].eq(as_of).all():fail('LOT_SNAPSHOT_DATE_MISMATCH','Snapshot_Date','로트 수량의 기준일이 분석 기준일과 다릅니다.',table='Lots')
            if lots.duplicated(['Item_ID','Lot_ID']).any():fail('DUPLICATE_LOT','Lot_ID','품목·로트 키가 중복됩니다.',table='Lots')
            if not set(lots['Item_ID'])<=set(o['Item_ID']):fail('UNKNOWN_LOT_ITEM','Item_ID','기초 수량에 없는 품목의 로트가 있습니다.',table='Lots')
            receipt=date_values(lots['Receipt_Date'],'Receipt_Date','Lots')
            if receipt.gt(end).any():fail('FUTURE_RECEIPT','Receipt_Date','기준일 이후 로트 입고일이 있습니다.',table='Lots')
            qty=pd.to_numeric(lots['Remaining_Quantity'],errors='coerce')
            if qty.isna().any() or not np.isfinite(qty.to_numpy(dtype=float,na_value=np.nan)).all() or qty.lt(0).any():
                fail('INVALID_LOT_QUANTITY','Remaining_Quantity','로트 잔여 수량은 0 이상의 유한한 수여야 합니다.',table='Lots')
            lots['Remaining_Quantity']=qty
            lots['Age_Days']=(end-receipt).dt.days
            lots['Age_Bucket']=pd.cut(lots['Age_Days'],bins=[-1,30,90,180,365,float('inf')],labels=['0-30','31-90','91-180','181-365','366+']).astype('string')
            sums=lots.groupby('Item_ID')['Remaining_Quantity'].sum().reset_index(name='Lot_Quantity')
            lot_recon=result[['Item_ID','Ending_Quantity']].merge(sums,on='Item_ID',how='left')
            lot_recon['Difference']=lot_recon['Lot_Quantity']-lot_recon['Ending_Quantity']
            # 수량 부동소수점 계산 오차만 구분한다. 금액 차이의 허용오차로 사용하지 않는다.
            lot_recon['Status']='quantity_match'
            lot_recon.loc[lot_recon['Difference'].abs().gt(1e-8),'Status']='quantity_mismatch'
            lot_recon.loc[lot_recon['Lot_Quantity'].isna(),'Status']='lot_not_provided'
            valid_items=set(lot_recon.loc[lot_recon['Status'].eq('quantity_match'),'Item_ID'])
            lots['Quantity_Check_Status']=lots['Item_ID'].map(lot_recon.set_index('Item_ID')['Status'])
            lots['Stale_Lot_Candidate']=lots['Age_Days'].ge(stale_days)&lots['Remaining_Quantity'].gt(0)
            lot_aging=lots
            valid_lots=lots.loc[lots['Item_ID'].isin(valid_items)]
            aging_buckets=valid_lots.groupby(['Item_ID','Age_Bucket'])['Remaining_Quantity'].sum().reset_index()
            lot_status='ready' if lot_recon['Status'].eq('quantity_match').all() else 'quantity_review_required'
            for _,row in lot_recon.loc[~lot_recon['Status'].eq('quantity_match')].iterrows():
                issues.append({'code':'LOT_QUANTITY_NOT_RECONCILED','field':'Remaining_Quantity','message':'수불 기말 수량과 로트 잔여 수량이 연결되지 않습니다.',
                    'source_file':'Lots','Item_ID':row['Item_ID'],'suggested_review':'동일 기준일·창고·품목 범위의 로트 잔여 수량을 확인하세요.'})
        except DataValidationError as error:
            lot_status='not_executed_input_issue';issues.extend(error.to_dict()['errors'])
    return AnalysisResult('inventory',{'item_count':len(result),'negative_stock_count':int(result['Negative_Stock'].sum()),
        'stale_candidate_count':int(result['Stale_Candidate'].sum()),
        'no_outflow_positive_stock_count':int((result['Ending_Quantity'].gt(0)&result['No_Outflow_In_Data']).sum()),
        'negative_movement_event_count':len(negative_events),'lot_aging_status':lot_status},
        {'item_summary':result,'review_items':result.loc[result['Review_Required']].copy(),
         'movement_timeline':timeline.drop(columns='_date'),'monthly_movements':monthly,'negative_events':negative_events.drop(columns='_date'),
         'lot_aging':lot_aging,'lot_quantity_reconciliation':lot_recon,'aging_buckets':aging_buckets,'module_issues':pd.DataFrame(issues)},
        {'as_of':as_of,'stale_days':stale_days,'lot_aging_status':lot_status,'quantity_roundoff_tolerance':1e-8,
         'timeline_basis':'제출 기초 수량과 일자·원본 행 순서로 계산합니다. 같은 날의 실제 처리 순서 또는 모집단 완전성을 보증하지 않습니다.',
         'limitation':'미출고 경과일은 로트 연령이 아닙니다. 로트 연령은 동일 기준일 잔여 수량이 수불 기말과 연결되는 품목만 집계합니다. 재고 금액·저가법·실사 결론은 별도 검토입니다.'})
