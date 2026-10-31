"""이미 확보한 조회 회신 정리표와 장부의 비교. 발송·진위 확인은 수행하지 않는다."""
import pandas as pd
from .common import AnalysisResult, columns, text, money, date_values, fail

AR_KEYS=['Business_Unit_Code','Counterparty_ID','Currency','As_Of_Date']
BANK_KEYS=['Business_Unit_Code','Institution_ID','Account_ID','Item_Type','Currency','As_Of_Date']
TERMS=['Interest_Rate','Maturity_Date','Collateral','Guarantees','Restrictions','Other_Arrangements']
STATUSES={'confirmed','disputed','partial','unable'}


def _prepare(frame,required,slot):
    columns(frame,required,slot)
    result=frame.copy().reset_index(drop=True)
    for c in required:result[c]=text(result,c,slot)
    result['_source_row']=range(2,len(result)+2)
    return result


def review_confirmations(ledger,requests,replies,*,as_of,kind='ar',amount_tolerance=0):
    if kind not in ('ar','bank'):raise ValueError('unsupported confirmation type')
    date_values(pd.Series([as_of]),'as_of','Parameters')
    tolerance=money(pd.Series([amount_tolerance]),'amount_tolerance','Parameters').iloc[0]
    if tolerance<0:fail('INVALID_TOLERANCE','amount_tolerance','허용 차이는 0 이상이어야 한다.',table='Parameters')
    keys=AR_KEYS if kind=='ar' else BANK_KEYS
    l=_prepare(ledger,keys,'ledger')
    q=_prepare(requests,['Request_ID',*keys],'requests')
    a=_prepare(replies,['Request_ID',*keys[:-1],'Response_Status','Reply_As_Of_Date','Evidence_Reference'],'replies')
    columns(l,['Balance'],'ledger')
    columns(a,['Confirmed_Balance'],'replies')
    for slot,frame in [('ledger',l),('requests',q)]:
        date_values(frame['As_Of_Date'],'As_Of_Date',slot)
        if frame['As_Of_Date'].ne(as_of).any():fail('CONFIRMATION_DATE_SCOPE','As_Of_Date','장부·요청 정리표는 분석 기준일과 동일한 자료를 제출한다.',table=slot)
        if not frame['Currency'].str.fullmatch('[A-Z]{3}').all():fail('INVALID_CURRENCY','Currency','통화는 대문자 3자리 코드로 지정한다.',table=slot)
        if frame.duplicated(keys,keep=False).any():fail('DUPLICATE_CONFIRMATION_SCOPE','*','같은 단위·대상·통화·기준일 항목이 중복된다. 합산 또는 재회신 선택 근거를 확인해 정리한다.',table=slot)
    if q['Request_ID'].duplicated().any():fail('DUPLICATE_REQUEST_ID','Request_ID','항목별 요청 ID는 유일해야 한다.',table='requests')
    if a['Request_ID'].duplicated().any():fail('MULTIPLE_REPLIES','Request_ID','한 항목에 회신이 여러 건이다. 최종 회신을 근거에 따라 선택해 제출한다.',table='replies')
    if not a['Response_Status'].isin(STATUSES).all():fail('INVALID_REPLY_STATUS','Response_Status','confirmed, disputed, partial, unable 중 하나를 지정한다.',table='replies')
    if not a['Currency'].str.fullmatch('[A-Z]{3}').all():fail('INVALID_CURRENCY','Currency','회신 통화를 확인한다.',table='replies')
    date_values(a['Reply_As_Of_Date'],'Reply_As_Of_Date','replies')
    l['_balance']=money(l['Balance'],'Balance','ledger')
    # 금액이 없는 회신은 명시적으로 비교 불가로 남긴다. 확인 회신에는 금액이 필수다.
    a['_balance']=pd.Series([None]*len(a),dtype=object)
    present=a['Confirmed_Balance'].astype('string').fillna('').str.strip().ne('')
    for i in a.index:
        if present.iloc[i]:a.at[i,'_balance']=int(money(pd.Series([a.at[i,'Confirmed_Balance']]),'Confirmed_Balance','replies').iloc[0])
        elif a.at[i,'Response_Status']=='confirmed':fail('CONFIRMED_BALANCE_REQUIRED','Confirmed_Balance','confirmed 회신에는 확인 금액이 필요하다.',table='replies',row=i+2)
    li={tuple(row[k] for k in keys):row for row in l.to_dict('records')}
    qi={tuple(row[k] for k in keys):row for row in q.to_dict('records')}
    ai={row['Request_ID']:row for row in a.to_dict('records')}
    rows=[];terms=[]
    for key in dict.fromkeys([*li,*qi]):
        book=li.get(key);request=qi.get(key);reply=ai.get(request['Request_ID']) if request else None
        status='not_requested' if request is None else 'no_reply' if reply is None else 'ledger_missing' if book is None else 'scope_mismatch' if any(reply[k]!=request[k] for k in keys[:-1]) else 'date_mismatch' if reply['Reply_As_Of_Date']!=as_of else reply['Response_Status'] if reply['Response_Status']!='confirmed' else 'comparable'
        difference=None
        if status=='comparable':
            difference=int(book['_balance'])-int(reply['_balance'])
            status='matched' if difference==0 else 'within_tolerance' if abs(difference)<=tolerance else 'difference'
        row={**dict(zip(keys,key)),'Request_ID':request['Request_ID'] if request else '',
             'Book_Balance':int(book['_balance'])/100 if book else None,'Confirmed_Balance':int(reply['_balance'])/100 if reply and reply['_balance'] is not None else None,
             'Difference':difference/100 if difference is not None else None,'Status':status,
             'Response_Status':reply['Response_Status'] if reply else '', 'Reply_As_Of_Date':reply['Reply_As_Of_Date'] if reply else '',
             'Reply_Scope':'; '.join(f'{k}={reply[k]}' for k in keys[:-1]) if reply else '',
             'Evidence_Reference':reply['Evidence_Reference'] if reply else '',
             'Ledger_Source_Row':book['_source_row'] if book else None,'Request_Source_Row':request['_source_row'] if request else None,'Reply_Source_Row':reply['_source_row'] if reply else None,
             'Terms_Review_Required':False,'Review_Status':'미검토','Suggested_Review':'회신 원본·진위·잔액 범위와 차이 원인을 확인하고 후속 절차를 기록한다.'}
        rows.append(row)
        if kind=='bank' and reply:
            for field in TERMS:
                def value(record):
                    v=record.get(field) if record else None
                    return '' if v is None or pd.isna(v) else str(v).strip()
                bv,rv=value(book),value(reply)
                state='not_provided' if not rv else 'not_in_ledger' if not bv else 'text_equal_unverified' if bv==rv else 'text_difference'
                if state!='text_equal_unverified':row['Terms_Review_Required']=True
                terms.append({**dict(zip(keys,key)),'Request_ID':row['Request_ID'],'Field':field,'Book_Value':bv,'Reply_Value':rv,'Status':state,'Evidence_Reference':reply['Evidence_Reference'],'Ledger_Source_Row':row['Ledger_Source_Row'],'Request_Source_Row':row['Request_Source_Row'],'Reply_Source_Row':row['Reply_Source_Row'],'Review_Status':'미검토'})
    result_columns=[*keys,'Request_ID','Book_Balance','Confirmed_Balance','Difference','Status','Response_Status','Reply_As_Of_Date','Reply_Scope','Evidence_Reference','Ledger_Source_Row','Request_Source_Row','Reply_Source_Row','Terms_Review_Required','Review_Status','Suggested_Review']
    comparison=pd.DataFrame(rows,columns=result_columns)
    orphan=a.loc[~a['Request_ID'].isin(q['Request_ID'])].drop(columns=['_balance']).rename(columns={'_source_row':'Reply_Source_Row'})
    # replies-only entries are never discarded or treated as matched balances.
    orphan=orphan.assign(Status='unknown_request',Review_Status='미검토')
    review=comparison.loc[comparison['Status'].ne('matched')|comparison['Terms_Review_Required'].astype(bool)].copy()
    summary={'ledger_row_count':len(l),'request_count':len(q),'reply_count':len(a),'matched_count':int(comparison['Status'].eq('matched').sum()),'review_row_count':len(review)+len(orphan),'no_reply_count':int(comparison['Status'].eq('no_reply').sum()),'not_requested_count':int(comparison['Status'].eq('not_requested').sum()),'difference_count':int(comparison['Status'].eq('difference').sum()),'orphan_reply_count':len(orphan)}
    tables={'confirmation_comparison':comparison,'review_items':review,'unlinked_replies':orphan}
    if kind=='bank':
        tables['terms_review']=pd.DataFrame(terms,columns=[*keys,'Request_ID','Field','Book_Value','Reply_Value','Status','Evidence_Reference','Ledger_Source_Row','Request_Source_Row','Reply_Source_Row','Review_Status'])
        summary['terms_review_count']=len(terms)
    return AnalysisResult('ar_confirmation' if kind=='ar' else 'bank_confirmation',summary,tables,{'as_of':as_of,'amount_tolerance':str(amount_tolerance),'difference_formula':'장부 잔액 - 회신 잔액. 같은 기준일의 confirmed 회신만 비교한다.','scope':'입력된 회신 정리표 비교. 요청 ID는 항목별 내부 식별자다. 요청 ID로 연결한 뒤 단위·대상·통화·기준일을 대조한다. 원문 전사 정확성은 별도 확인한다.','limitation':'조회서 발송·회수 통제·진위 확인·미회신 대체절차·감사 결론을 수행하지 않는다. 일치해도 미검토 상태이며 전체 조회 범위를 보증하지 않는다. 금융기관 조건은 문자열 비교이며 공란은 없음이 아니다.'})


def ar_confirmation_review(ledger,requests,replies,*,as_of,amount_tolerance=0):
    return review_confirmations(ledger,requests,replies,as_of=as_of,kind='ar',amount_tolerance=amount_tolerance)


def bank_confirmation_review(ledger,requests,replies,*,as_of,amount_tolerance=0):
    return review_confirmations(ledger,requests,replies,as_of=as_of,kind='bank',amount_tolerance=amount_tolerance)
