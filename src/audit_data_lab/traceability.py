"""원본 행, 계산 정의와 결과 행의 연결. 임의로 전체 출처 추적을 주장하지 않는다."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import pandas as pd

TRACE_VERSION='1'
FORMULAS={
 'year_comparison':{'Current_Movement':'당기 D 금액 합계 - 당기 C 금액 합계','Prior_Movement':'전기 D 금액 합계 - 전기 C 금액 합계','Change':'Current_Movement - Prior_Movement','Change_Pct':'(Current_Movement - Prior_Movement) / abs(Prior_Movement) * 100; 분모 0이면 계산 불가'},
 'monthly_comparison':{'Current_Movement':'당기 해당 회계기간 D 금액 합계 - C 금액 합계','Prior_Movement':'전기 해당 회계기간 D 금액 합계 - C 금액 합계','Change':'Current_Movement - Prior_Movement','Change_Pct':'(Current_Movement - Prior_Movement) / abs(Prior_Movement) * 100; 누락·분모 0이면 계산 불가'},
 'balance_comparison':{'Balance_Change':'Current_Balance - Prior_Balance','Balance_Change_Pct':'(Current_Balance - Prior_Balance) / abs(Prior_Balance) * 100'},
 'financial_ratios':{'Current_Ratio':'유동자산 / 유동부채','Working_Capital':'유동자산 - 유동부채','Debt_To_Equity':'(유동부채 + 비유동부채) / 자본'},
 'item_summary':{'Ending_Quantity':'Opening_Quantity + sum(Quantity_In) - sum(Quantity_Out)'},
 'review_items':{'inventory':'Opening_Quantity + sum(Quantity_In) - sum(Quantity_Out)'},
 'matches':{'Amount':'같은 계좌·통화·부호 금액; 설정 일자 차이 이내의 상호 유일 후보만 연결'},
 'balance_reconciliation':{'Difference':'Bank_Balance + Bank_Adjustment - GL_Balance'},
 'lot_aging':{'Age_Days':'as_of - Receipt_Date; 기말 로트 수량 대사 상태 별도 확인'},
}

def records(frame):
    return json.loads(frame.to_json(orient='records',date_format='iso',force_ascii=False))

def frame_digest(frame):
    return sha256(frame.to_csv(index=False,lineterminator='\n').encode()).hexdigest()

def attach_traceability(result,frames,assets,*,run_id,parameters=None):
    """행번호는 헤더 1행을 전제로 한 논리 레코드 번호. CSV 물리 줄 번호와 다를 수 있다."""
    sources={};indices={}
    indexed_fields={'Business_Unit_Code','GL_Account_Number','Amount_Currency','Fiscal_Year','Period','Journal_ID','Item_ID','Lot_ID','Bank_Account','Currency','Row_ID','Date','Snapshot_Date'}
    for slot,frame in frames.items():
        asset=assets.get(slot,{})
        sources[slot]={**{k:v for k,v in asset.items() if k not in {'stored_name','history'}},
            'dataset_version_id':asset.get('version_id',frame_digest(frame)),
            'parsed_sha256':frame_digest(frame),'columns':list(frame.columns),'row_count':len(frame),
            'sheet':asset.get('sheet','first worksheet' if asset.get('suffix')=='.xlsx' else None),
            'first_data_row':asset.get('first_data_row',2),
            'row_basis':asset.get('row_basis','헤더=1, 첫 논리 데이터 레코드=2. CSV 여러 줄 셀은 물리 줄 번호와 다름'),
            'previous_versions':[{k:v for k,v in h.items() if k!='stored_name'} for h in asset.get('history',[])]}
        ix={}
        for field in indexed_fields.intersection(frame.columns):
            grouped={}
            for pos,value in enumerate(frame[field].astype('string').fillna('')):
                key=str(value).strip()
                if field=='Period':key=key.zfill(2)
                grouped.setdefault(key,set()).add(pos+asset.get('first_data_row',2))
            ix[field]=grouped
        indices[slot]=ix
    def select(slot,filters):
        if slot not in frames:return []
        found=None
        for field,value in filters.items():
            if value is None:continue
            if field not in indices[slot]:return []
            key=str(value).strip();key=key.zfill(2) if field=='Period' else key
            rows=indices[slot][field].get(key,set())
            found=rows.copy() if found is None else found.intersection(rows)
        return sorted(found) if found is not None else list(range(sources[slot]['first_data_row'],len(frames[slot])+sources[slot]['first_data_row']))
    def ref(slot,rows,role):
        return {'slot':slot,'dataset_version_id':sources[slot]['dataset_version_id'],'rows':rows,'role':role} if slot in sources and rows else None
    sap_lineage=records(result.tables['sap_lineage']) if result.name=='sap_preprocessing' and 'sap_lineage' in result.tables else []
    tables={};trace={}
    for name,frame in list(result.tables.items()):
        data=records(frame);out=[]
        for pos,row in enumerate(data):
            rid=sha256(f'{run_id}\0{name}\0{pos}'.encode()).hexdigest()[:24]
            refs=[];status='unavailable';definition=FORMULAS.get(name,{})
            if name=='review_items':definition={'Ending_Quantity':'Opening_Quantity + sum(Quantity_In) - sum(Quantity_Out)'} if result.name=='inventory' else {}
            if name in {'movement_timeline','negative_events'}:definition={'Running_Quantity':'기초 수량 + 해당 일자·원본 행까지 누적 (Quantity_In - Quantity_Out); 같은 날 실제 시간 순서는 미확인'}
            if name=='monthly_movements' and result.name=='inventory':definition={'Net_Quantity':'해당 품목·월 Quantity_In 합계 - Quantity_Out 합계'}
            def add(slot,rows,role):
                value=ref(slot,rows,role)
                if value:refs.append(value)
            if result.name=='quickbooks_preprocessing' and row.get('QuickBooks_Source_Row') is not None:
                add('quickbooks',[int(row['QuickBooks_Source_Row'])],'QuickBooks 원본 보고서 행')
                if name=='modified_gl' and row.get('Account_Source_Row') is not None:
                    add('quickbooks',[int(row['Account_Source_Row'])],'실제로 연결한 계정 표제 또는 거래행 자체 계정 표시')
                status='source_rows' if refs else 'unavailable'
                definition={'conversion':'계정 표제 연결, 지정 날짜 형식 해석, 쉼표·괄호 금액 표준화. ADS 변환은 수행하지 않음.'}
            elif result.name=='sap_preprocessing' and name in {'gl','sap_supplement','sap_lineage'}:
                lineage=sap_lineage[pos]
                add('bseg',[int(lineage['BSEG_Source_Row'])],'SAP 상세 원본 행')
                add('bkpf',[int(lineage['BKPF_Source_Row'])],'회사·연도·전표번호로 결합한 SAP 헤더 행')
                status='source_rows' if refs else 'unavailable'
                definition={'conversion':'회사·연도·전표번호로 BSEG와 BKPF 결합. S/H→D/C, 금액·일자·기간 검증. GL/TB 대사 결과는 별도 표 참조.'}
            elif result.name in {'ar_confirmation','bank_confirmation'}:
                for slot,column in [('ledger','Ledger_Source_Row'),('requests','Request_Source_Row'),('replies','Reply_Source_Row')]:
                    value=row.get(column)
                    if value is not None:add(slot,[int(value)],'조회 회신 비교 원본 행')
                status='source_rows' if refs else 'unavailable'
                definition={'Difference':'동일 기준일 confirmed 회신의 장부 잔액 - 회신 잔액. 기타 상태는 계산하지 않는다.','terms':'금융기관 조건 문자열 비교. 원문·진위 검토는 별도다.'}
            elif result.name=='gl_user_split':
                if row.get('Split_Source_Row') is not None:add('gl',[int(row['Split_Source_Row'])],'분할 전 원본 GL 행')
                elif name=='row_membership':add('gl',[int(row['Source_Row'])],'분할 그룹 원본 GL 행')
                elif name=='group_index':
                    members=result.tables['row_membership']
                    add('gl',members.loc[members['Group_ID'].eq(row['Group_ID']),'Source_Row'].astype(int).tolist(),'해당 입력 사용자 그룹 원본 GL 행')
                status='source_rows' if refs else 'unavailable'
                definition={'split':'입력 사용자 컬럼 값별 행 선택. 원본 값·순서 유지; 미확보 사용자는 별도 그룹.'}
            elif result.name=='analytical_review' and name in {'year_comparison','monthly_comparison','monthly_movements','balance_comparison','financial_ratios','ratio_components'}:
                slot='tb' if name in {'balance_comparison','financial_ratios','ratio_components'} else 'gl'
                filters={k:row[k] for k in ['Business_Unit_Code','GL_Account_Number','Amount_Currency'] if k in row}
                if name in {'monthly_comparison','monthly_movements'}:filters['Period']=row.get('Period')
                if slot=='tb':filters['Period']=(parameters or {}).get('tb_period')
                years=[row['Fiscal_Year']] if 'Fiscal_Year' in row else [result.metadata.get('current_year'),result.metadata.get('prior_year')]
                for year in years:
                    if year is not None:add(slot,select(slot,{**filters,'Fiscal_Year':year}),f'Fiscal_Year={year}')
                if slot=='tb' and 'account_mapping' in frames:add('account_mapping',select('account_mapping',{k:v for k,v in filters.items() if k in {'Business_Unit_Code','GL_Account_Number'}}),'계정 분류·부호 정의')
                status='group_inputs' if refs else 'unavailable'
            elif result.name=='jet' and 'Journal_ID' in row:
                if 'Source_Row' in row and row['Source_Row'] is not None:
                    add('gl',[int(row['Source_Row'])],'탐지된 GL 행')
                else:add('gl',select('gl',{'Journal_ID':row['Journal_ID'],**({'Amount_Currency':row['Amount_Currency']} if 'Amount_Currency' in row else {})}),'전표 구성행')
                status='source_rows' if refs else 'unavailable'
                definition={'selection':row.get('Selection_Reason',row.get('Selection_Reasons','규칙 설정과 Rule_ID를 함께 확인하세요.')),'limitation':'저빈도·중복 등 규칙은 전체 모집단에도 의존합니다. 연결 행만으로 규칙 재수행이 완결되지는 않습니다.'}
            elif result.name=='cash_proofing':
                for slot,key in [('bank','Row_ID_Bank'),('cash_gl','Row_ID_GL')]:
                    if key in row:add(slot,select(slot,{'Row_ID':row[key]}),'연결 후보 거래')
                if 'Row_ID' in row:
                    slot='bank' if name=='unmatched_bank' or row.get('Side')=='Bank' else 'cash_gl'
                    add(slot,select(slot,{'Row_ID':row['Row_ID']}),'검토 거래')
                if name=='balance_reconciliation':add('balances',select('balances',{k:row[k] for k in ['Bank_Account','Currency'] if k in row}),'제출 잔액·조정')
                status='source_rows' if refs else 'unavailable'
            elif result.name=='inventory' and 'Item_ID' in row:
                filters={'Item_ID':row['Item_ID']}
                for slot in ['opening','movements','lot_snapshot']:
                    chosen=dict(filters)
                    if slot=='lot_snapshot' and 'Lot_ID' in row:chosen['Lot_ID']=row['Lot_ID']
                    rows=select(slot,chosen)
                    if slot=='movements' and name in {'movement_timeline','negative_events'} and row.get('Source_Row') is not None:
                        # 날짜/행 순의 누적 계산 입력만 선택한다.
                        f=frames[slot];cutoff=(str(row['Date']),int(row['Source_Row']))
                        rows=[n for n in rows if (str(f.iloc[n-2]['Date']),n)<=cutoff]
                    if slot=='movements' and name=='monthly_movements':rows=[n for n in rows if str(frames[slot].iloc[n-2]['Date'])[:6]==str(row['Period']).replace('-','')]
                    add(slot,rows,'품목 계산 입력; 표별 산식·범위를 함께 확인')
                status='group_inputs' if refs else 'unavailable'
            elif result.name=='data_cleansing' and name=='mapped_data':
                add('data',[pos+2],'이름 변경 전 원본 행')
                if 'mapping' in frames:add('mapping',select('mapping',{}),'사용자 지정 컬럼 매핑')
                status='source_rows'
            entry={'review_id':rid,'table':name,'record_index':pos,'status':status,'sources':refs,'calculation':definition,
                'conditions':parameters or {},'note':'source_rows는 원본 행 연결, group_inputs는 집계 입력 범위 연결입니다. unavailable은 출처 연결 미구현 또는 해당 없음입니다.'}
            trace[rid]=entry;out.append({'review_id':rid,'values':row,'lineage_status':status})
        tables[name]={'columns':list(frame.columns),'rows':out,'row_count':len(out)}
        # CSV 조서에서도 웹 결과와 연결할 수 있는 같은 ID를 제공한다.
        if 'Review_Record_ID' not in frame:
            copy=frame.copy();copy.insert(0,'Review_Record_ID',[r['review_id'] for r in out]);result.tables[name]=copy
    manifest={'schema_version':TRACE_VERSION,'run_id':run_id,'created_at':datetime.now(timezone.utc).isoformat(),
        'module':result.name,'summary':result.summary,'metadata':result.metadata,'datasets':sources,'tables':tables,'trace':trace,
        'scope':'이번 작업에 업로드한 자료부터 분석 결과까지 연결합니다. 사전 SAP→ADS 변환 이력이나 SAP 시스템 추출 원본까지 자동 소급하지 않습니다.',
        'calculation_policy':'현재 코드의 선언된 산식 및 조건 기록입니다. 실행 이벤트 전체나 원본 시스템 추출 완전성 증명은 아닙니다.'}
    result.metadata['traceability']={'schema_version':TRACE_VERSION,'run_id':run_id,'source_versions':{s:d['dataset_version_id'] for s,d in sources.items()},'manifest':'review_snapshot.json'}
    return manifest
