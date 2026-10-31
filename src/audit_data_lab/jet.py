"""GL·로그 모집단 대사와 규칙 기반 Journal Entry Testing.
탐지는 후속 검토 후보이며 오류·부정의 확정 판단이 아니다.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import pandas as pd
from .common import AnalysisResult, columns, date_values, fail, money, prepare_gl, text
from .reconciliation_basis import check_log_basis

@dataclass(frozen=True)
class JetConfig:
    round_unit: int=1000
    rare_user_max: int=10
    rare_account_max: int=3
    night_start: int=20
    night_end: int=6
    # 통화별 기준을 사용한다. 미설정 통화에는 고액 규칙을 적용하지 않는다.
    large_amounts: dict=field(default_factory=dict)
    manual_sources: tuple=()
    closing_dates: tuple=()
    combined_rule_min: int=2


def adapt_legacy_log(log, *, company, fiscal_year, currency=None):
    """기존 예제의 BELNR·S/H 로그를 명시적으로 지정한 단일 범위의 ADS 키로 변환.
    원본 로그에 회사/연도/통화가 없으므로 호출자가 범위를 확인해야 한다.
    """
    if currency is not None:
        fail('UNVERIFIED_CURRENCY_OVERRIDE','Amount_Currency','기존 로그에 통화를 임의 부여할 수 없습니다. 근거·검토 기록을 포함한 대사 기준 확인서가 필요합니다.',table='Log')
    columns(log,['Journal_ID','Amount_Credit_Debit_Indicator','Total'],'Log')
    result=log.copy().reset_index(drop=True)
    identifiers=text(result,'Journal_ID','Log')
    if identifiers.str.contains(':',regex=False).any():
        fail('ALREADY_SCOPED_LOG','Journal_ID','이미 복합 키인 로그에는 기존 예제 변환을 적용하지 마세요.',table='Log')
    dc=result['Amount_Credit_Debit_Indicator'].astype('string').str.strip().map({'S':'D','H':'C'})
    if dc.isna().any():fail('INVALID_DC_CODE','Amount_Credit_Debit_Indicator','기존 로그는 SAP S/H 코드여야 합니다.',table='Log')
    result['Journal_ID']=str(company)+':'+str(fiscal_year)+':'+identifiers
    result['Amount_Credit_Debit_Indicator']=dc
    # 통화를 만들거나 변경하지 않습니다. 회사·연도 지정도 검토 근거 없이는 확인 완료가 아닙니다.
    result.attrs['legacy_scope_unverified']={'company':str(company),'fiscal_year':str(fiscal_year)}
    return result


def run_jet(gl, log, config=None, *, log_basis=None, evidence_root=None):
    config=config or JetConfig()
    if config.round_unit<=0 or config.rare_user_max<0 or config.rare_account_max<0:
        raise ValueError('금액 단위와 빈도 기준을 확인하세요.')
    if not 0<=config.night_end<config.night_start<=23:
        raise ValueError('야간 기준은 종료 시간 < 시작 시간인 0~23시여야 합니다.')
    if isinstance(config.combined_rule_min,bool) or not isinstance(config.combined_rule_min,int) or config.combined_rule_min<2:
        raise ValueError('복합 조건은 서로 다른 규칙 2개 이상으로 설정하세요.')
    g=prepare_gl(gl)
    columns(log,['Journal_ID','Amount_Credit_Debit_Indicator','Total'],'Log')
    l=log.copy().reset_index(drop=True)
    for c in ['Journal_ID','Amount_Credit_Debit_Indicator']:l[c]=text(l,c,'Log')
    if not l['Amount_Credit_Debit_Indicator'].isin(['D','C']).all():
        fail('INVALID_DC_CODE','Amount_Credit_Debit_Indicator','로그에 ADS D/C 코드가 필요합니다.',table='Log')
    basis_check=check_log_basis(gl,log,log_basis,evidence_root=evidence_root)
    control_keys=['Journal_ID','Amount_Currency','Amount_Credit_Debit_Indicator']
    control_columns=control_keys+['GL_Total_Cents','Log_Total_Cents','Match_Status','Difference_Cents','Difference']
    control_exceptions=pd.DataFrame(columns=control_columns)
    population=pd.DataFrame(columns=['Journal_ID','Amount_Currency','Match_Status'])
    amount_status=basis_check.status
    population_status=basis_check.status
    if basis_check.status=='ready':
        # 근거 확인이 끝난 복사본에서만 통화를 설정합니다. 원본 로그는 변경하지 않습니다.
        l['Amount_Currency']=basis_check.log_currency.reset_index(drop=True)
        l['_total_cents']=money(l['Total'],'Total','Log')
        totals=g.groupby(control_keys)['_amount_cents'].sum().reset_index(name='GL_Total_Cents').merge(
            l.groupby(control_keys)['_total_cents'].sum().reset_index(name='Log_Total_Cents'),
            on=control_keys,how='outer',indicator=True)
        totals['Match_Status']=totals.pop('_merge').astype('string')
        totals[['GL_Total_Cents','Log_Total_Cents']]=totals[['GL_Total_Cents','Log_Total_Cents']].fillna(0).astype('int64')
        totals['Difference_Cents']=totals['GL_Total_Cents']-totals['Log_Total_Cents']
        totals['Difference']=totals['Difference_Cents']/100
        control_exceptions=totals.loc[totals['Difference_Cents'].ne(0)|totals['Match_Status'].ne('both')].copy()
        population=g[['Journal_ID','Amount_Currency']].drop_duplicates().merge(
            l[['Journal_ID','Amount_Currency']].drop_duplicates(),on=['Journal_ID','Amount_Currency'],how='outer',indicator=True)
        population['Match_Status']=population.pop('_merge').astype('string')
        amount_status='differences_found' if len(control_exceptions) else 'matched'
        population_status='differences_found' if population['Match_Status'].ne('both').any() else 'matched'
    balance=g.groupby(['Journal_ID','Amount_Currency'])['_net_cents'].transform('sum')
    entered=date_values(g['Entered_Date'],'Entered_Date','GL')
    flags=[];counts={};skipped=[]
    def flag(rule,mask,reason,review):
        mask=mask.fillna(False)
        counts[rule]={'row_count':int(mask.sum()),'journal_count':int(g.loc[mask,'Journal_ID'].nunique())}
        part=g.loc[mask,[c for c in gl.columns if c in g]].copy()
        part['Source_Row']=g.loc[mask,'_source_row']
        part['Rule_ID']=rule;part['Selection_Reason']=reason;part['Suggested_Review']=review
        flags.append(part)
    flag('UNBALANCED_JOURNAL',balance.ne(0),'전표의 차변·대변 순액이 0이 아닙니다.','모집단 범위와 전표 상세 누락 여부 확인')
    duplicate_keys=['Business_Unit_Code','Fiscal_Year','Period','GL_Account_Number','Amount_Currency','Amount_Credit_Debit_Indicator','_amount_cents']
    repeat=g.groupby(duplicate_keys)['Journal_ID'].transform('nunique').gt(1)
    flag('REPEATED_ACCOUNT_AMOUNT',repeat,'같은 기간·계정·차대변·금액이 여러 전표에서 반복됩니다.','정기 거래인지 중복 기록인지 증빙 확인')
    flag('ROUND_AMOUNT',g['_amount_cents'].ne(0)&g['_amount_cents'].mod(config.round_unit*100).eq(0),
         f'금액이 {config.round_unit} 통화 단위의 배수입니다.','정액 거래의 계약·산출 근거 확인')
    flag('WEEKEND_ENTRY',entered.dt.dayofweek.ge(5),'주말에 입력한 전표입니다.','업무 일정·입력 권한·승인 내역 확인')
    if 'Entered_Time' in g:
        values=g['Entered_Time'].astype('string').str.strip()
        width=values.str.len()
        valid=values.str.fullmatch(r'\d{4}|\d{6}').fillna(False)
        normalized=values.where(width.eq(6),values+'00')
        times=pd.to_datetime(normalized,format='%H%M%S',errors='coerce')
        if not (valid & times.notna()).all():fail('INVALID_TIME','Entered_Time','입력시간은 HHMM 또는 HHMMSS여야 합니다.',table='GL')
        flag('NIGHT_ENTRY',times.dt.hour.ge(config.night_start)|times.dt.hour.lt(config.night_end),
             '설정한 야간 시간대에 입력한 전표입니다.','업무 일정·사용자·승인 내역 확인')
    else:skipped.append({'rule':'NIGHT_ENTRY','reason':'Entered_Time 미제공'})
    users=g.groupby('Entered_By')['Journal_ID'].transform('nunique')
    flag('RARE_USER',users.le(config.rare_user_max),'입력한 고유 전표 수가 설정 빈도 이하인 사용자입니다.','사용자의 역할·권한과 업무상 필요성 확인')
    accounts=g.groupby(['Business_Unit_Code','GL_Account_Number'])['Journal_ID'].transform('nunique')
    flag('RARE_ACCOUNT',accounts.le(config.rare_account_max),'사용된 고유 전표 수가 설정 빈도 이하인 계정입니다.','계정 성격과 거래 근거 확인')
    large=pd.Series(False,index=g.index)
    for currency,threshold in config.large_amounts.items():
        threshold_cents=int(money(pd.Series([threshold])).iloc[0])
        if threshold_cents<=0:raise ValueError('고액 기준은 양수여야 합니다.')
        large |= g['Amount_Currency'].eq(currency)&g['_amount_cents'].abs().ge(threshold_cents)
    if config.large_amounts:flag('LARGE_AMOUNT',large,'통화별로 설정한 고액 기준 이상입니다.','중요 거래의 계약·승인·회계처리 근거 확인')
    else:skipped.append({'rule':'LARGE_AMOUNT','reason':'통화별 고액 기준 미설정'})
    if config.manual_sources and config.closing_dates and 'Source' in g:
        date_values(pd.Series(config.closing_dates),'Closing_Date','Config')
        flag('CLOSING_MANUAL',g['Source'].isin(config.manual_sources)&g['Effective_Date'].isin(config.closing_dates),
             '설정한 결산일에 설정한 수동 출처로 기록한 전표입니다.','결산 조정 근거·승인·관련 증빙 확인')
    else:skipped.append({'rule':'CLOSING_MANUAL','reason':'검증된 수동 출처 코드 또는 결산일 미설정'})
    if 'Document_Date' in g:
        document=date_values(g['Document_Date'],'Document_Date','GL')
        flag('DOCUMENT_AFTER_ENTRY',document.gt(entered),'문서일이 시스템 입력일보다 나중입니다.','일자 차이의 업무상 이유와 증빙 확인')
    else:skipped.append({'rule':'DOCUMENT_AFTER_ENTRY','reason':'보조 필드 Document_Date 미제공'})
    flagged=pd.concat(flags,ignore_index=True)
    gap_rows=[];gap_skipped=0
    identities=g['Journal_ID'].drop_duplicates()
    parts=identities.str.rsplit(':',n=1,expand=True)
    if parts.shape[1]==2:
        valid=parts[1].str.fullmatch(r'\d+').fillna(False)
        gap_skipped=int((~valid).sum())
        seq=pd.DataFrame({'Scope':parts.loc[valid,0],'Number':parts.loc[valid,1]})
        for scope,items in seq.groupby('Scope'):
            nums=sorted(set(int(v) for v in items['Number']))
            for left,right in zip(nums,nums[1:]):
                if right-left>1:gap_rows.append({'Scope':scope,'Previous_Number':left,'Next_Number':right,'Missing_Count':right-left-1})
    else:gap_skipped=len(identities)
    gaps=pd.DataFrame(gap_rows,columns=['Scope','Previous_Number','Next_Number','Missing_Count'])
    # 상세행에 같은 규칙이 여러 번 나타나도 전표별 규칙 개수를 중복 계산하지 않는다.
    queue_rows=[]
    for (journal,currency),part in flagged.groupby(['Journal_ID','Amount_Currency']):
        source=g.loc[g['Journal_ID'].eq(journal)&g['Amount_Currency'].eq(currency)]
        rules=sorted(set(part['Rule_ID']))
        queue_rows.append({'Journal_ID':journal,'Amount_Currency':currency,'Matched_Rule_Count':len(rules),
            'Rules':', '.join(rules),'Complex_Condition':len(rules)>=config.combined_rule_min,
            'Debit_Total':int(source.loc[source['Amount_Credit_Debit_Indicator'].eq('D'),'_amount_cents'].sum())/100,
            'Credit_Total':int(source.loc[source['Amount_Credit_Debit_Indicator'].eq('C'),'_amount_cents'].sum())/100,
            'Selection_Reasons':' / '.join(sorted(set(part['Selection_Reason']))),
            'Suggested_Review':' / '.join(sorted(set(part['Suggested_Review']))),
            'Source_Rows':', '.join(str(v) for v in sorted(set(part['Source_Row'])))})
    queue=pd.DataFrame(queue_rows,columns=['Journal_ID','Amount_Currency','Matched_Rule_Count','Rules','Complex_Condition','Debit_Total','Credit_Total','Selection_Reasons','Suggested_Review','Source_Rows'])
    if len(queue):queue=queue.sort_values(['Matched_Rule_Count','Journal_ID'],ascending=[False,True]).reset_index(drop=True)
    return AnalysisResult('jet',{
        'input_row_count':len(g),'journal_count':int(g['Journal_ID'].nunique()),
        'complex_condition_journal_count':int(queue.loc[queue['Complex_Condition'].astype(bool),'Journal_ID'].nunique()),
        'flagged_row_count':int(flagged['Source_Row'].nunique()),
        'flagged_journal_count':int(flagged['Journal_ID'].nunique()),
        'rule_hit_count':len(flagged),
        'log_amount_reconciliation_status':amount_status,
        'log_population_status':population_status,
        'log_population_difference_count':int(population['Match_Status'].ne('both').sum()) if basis_check.status=='ready' else None,
        'log_control_exception_count':len(control_exceptions) if basis_check.status=='ready' else None,'sequence_gap_count':len(gaps),'rules':counts,
    },{'flagged_lines':flagged,'journal_review_queue':queue,'log_population':population,'log_control_exceptions':control_exceptions,'sequence_gaps':gaps,'log_basis_issues':basis_check.to_frame()},
       {'queue_interpretation':'규칙 개수별 정렬이며 검증된 위험 점수나 부정 확률이 아닙니다. 차변·대변 금액은 통화별로 분리합니다.',
        'config':asdict(config),'log_basis_confirmation':basis_check.metadata,
        'log_basis_status':basis_check.status,
        'analysis_scope':'GL 단독 검사는 입력 GL 범위에서 수행합니다. 로그 대사 미실행은 모집단 완전성 확인 완료를 의미하지 않습니다.',
        'skipped_rules':skipped,'sequence_non_numeric_skipped':gap_skipped,
        'interpretation':'검토 후보입니다. 오류·부정의 확정 판단이 아닙니다. 번호 공백은 발급 정책에 따라 정상일 수 있습니다.',
        'log_basis':'확인 근거·검토 기록·입력 연결을 확인한 경우에만 전표·통화·D/C별 금액을 대사합니다. 차단 상태의 빈 결과표는 일치를 의미하지 않습니다.'})
