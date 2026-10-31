"""SAP BSEG·BKPF·GLT0 → ADS GL/TB. 기존 노트북의 검증된 변환 로직."""
import calendar
import pandas as pd
from .validation import validate_sap_inputs
from .common import AnalysisResult, fail


def convert_sap_data(bseg,bkpf,glt0,*,company,year,ledger='0',record_type='0',version='1'):
    """입력을 변경하지 않고 GL·TB와 대사표를 반환. 달력연도·금액 소수 2자리 전제."""
    COMPANY,YEAR,LEDGER,RECORD_TYPE,VERSION=map(str,(company,year,ledger,record_type,version))
    bseg,bkpf,glt0=validate_sap_inputs(bseg,bkpf,glt0,company=COMPANY,year=YEAR,ledger=LEDGER,record_type=RECORD_TYPE,version=VERSION)
    try:
        def require(condition, message):
            if not condition:
                raise ValueError(message)
        keys = ['BUKRS (Company Code)', 'GJAHR (Fiscal Year)', 'BELNR (Accounting Document Number)']
        b = bseg.loc[bseg[keys[0]].eq(COMPANY) & bseg[keys[1]].eq(YEAR)].copy()
        h = bkpf.loc[bkpf[keys[0]].eq(COMPANY) & bkpf[keys[1]].eq(YEAR)].copy()
        require(not b.empty and (not h.empty), '선택 범위에 GL 데이터가 없습니다.')
        require(not b[keys].isna().any().any(), 'BSEG 전표 키에 결측값이 있습니다.')
        require(not h[keys].isna().any().any(), 'BKPF 전표 키에 결측값이 있습니다.')
        duplicates = h.loc[h.duplicated(keys, keep=False)]
        require(duplicates.empty, '헤더 키가 중복됩니다. duplicate_headers.csv를 확인하세요.')
        line_keys = keys + ['BUZEI (Number of Line Item Within Accounting Document)']
        require(not b[line_keys].isna().any().any(), '상세행 키에 결측값이 있습니다.')
        require(not b.duplicated(line_keys).any(), '상세행 키가 중복됩니다.')
        header_columns = keys + ['BKTXT (Document Header Text)', 'BLART (Document Type)', 'BUDAT (Posting Date in the Document)', 'BLDAT (Document Date in Document)', 'CPUDT (Day On Which Accounting Document Was Entered)', 'CPUTM (Time of Entry)', 'MONAT (Fiscal Period)', 'USNAM (User name)', 'HWAER (Local Currency)']
        merged = b.merge(h[header_columns], on=keys, how='left', validate='many_to_one', indicator=True)
        unmatched = merged.loc[merged['_merge'].eq('left_only')]
        require(unmatched.empty, '헤더 미연결 행이 있습니다. unmatched_details.csv를 확인하세요.')
        require(len(merged) == len(b), '결합 후 행 수가 바뀌었습니다.')

        def cents(values):
            from decimal import Decimal, InvalidOperation
            result = []
            for value in values:
                require(pd.notna(value), '금액에 결측값이 있습니다.')
                try:
                    number = Decimal(str(value))
                except InvalidOperation as exc:
                    raise ValueError(f'잘못된 금액: {value}') from exc
                require(number.is_finite(), f'유한하지 않은 금액: {value}')
                scaled = number * 100
                require(scaled == scaled.to_integral_value(), f'소수 둘째 자리 초과 금액: {value}')
                result.append(int(scaled))
            return pd.Series(result, index=values.index, dtype='int64')

        def dates(values):
            return pd.to_datetime(values, format='%Y%m%d', errors='raise').dt.strftime('%Y%m%d')
        m = merged
        indicator = m['SHKZG (Debit/Credit Indicator)'].map({'S': 'D', 'H': 'C'})
        require(indicator.notna().all(), '알 수 없는 차대변 코드가 있습니다.')
        amount_cents = cents(m['DMBTR (Amount in Local Currency)'])
        currency = m['HWAER (Local Currency)']
        require(currency.notna().all() and currency.nunique() == 1, '기능통화 기준을 확인하세요.')
        require(currency.str.fullmatch('[A-Z]{3}').fillna(False).all(), '통화는 영문 대문자 3자리 코드여야 합니다.')
        period_text = m['MONAT (Fiscal Period)']
        require(period_text.str.fullmatch('\\d{1,2}').fillna(False).all(), '회계기간은 정수 1~16이어야 합니다.')
        period = pd.to_numeric(period_text, errors='raise').astype(int)
        require(period.between(1, 16).all(), '회계기간 범위를 확인하세요.')
        posting = pd.to_datetime(m['BUDAT (Posting Date in the Document)'], format='%Y%m%d', errors='raise')
        require(posting.notna().all(), '전기일이 비어 있습니다.')
        require((posting.dt.year == int(YEAR)).all(), '달력연도와 회계연도가 다릅니다. 회계 달력 설정이 필요합니다.')
        require((posting.dt.month.loc[period <= 12] == period.loc[period <= 12]).all(), '달력 월과 회계기간이 다릅니다. 회계 달력 설정이 필요합니다.')
        require(((posting.dt.month == 12) & (posting.dt.day == 31)).loc[period >= 13].all(), '달력연도 기준 특별기간 13~16의 전기일은 연말이어야 합니다.')
        entered = dates(m['CPUDT (Day On Which Accounting Document Was Entered)'])
        require(entered.notna().all(), '입력일이 비어 있습니다.')
        time = m['CPUTM (Time of Entry)'].str.zfill(6)
        require(time.notna().all() and time.str.fullmatch('\\d{6}').all(), '입력시간 형식이 잘못됐습니다.')
        pd.to_datetime(time, format='%H%M%S', errors='raise')
        unit = m['BUKRS (Company Code)'] + ':' + m['GSBER (Business Area)'].fillna('')
        gl = pd.DataFrame({'Journal_ID': m[keys[0]] + ':' + m[keys[1]] + ':' + m[keys[2]], 'Journal_ID_Line_Number': m['BUZEI (Number of Line Item Within Accounting Document)'], 'JE_Header_Description': m['BKTXT (Document Header Text)'], 'JE_Line_Description': m['SGTXT (Item Text)'], 'Source': m['BLART (Document Type)'], 'Business_Unit_Code': unit, 'Effective_Date': posting.dt.strftime('%Y%m%d'), 'Fiscal_Year': m[keys[1]], 'Period': period.astype('string').str.zfill(2), 'GL_Account_Number': m['HKONT (General Ledger Account)'], 'Amount': amount_cents / 100, 'Amount_Credit_Debit_Indicator': indicator, 'Amount_Currency': currency, 'Entered_By': m['USNAM (User name)'], 'Entered_Date': entered, 'Entered_Time': time.str[:4], 'Reversal_Indicator': pd.NA})
        require(gl['GL_Account_Number'].notna().all(), '계정번호 누락이 있습니다.')
        signed_cents = amount_cents.where(indicator.eq('D'), -amount_cents)
        require((cents(gl['Amount']) == amount_cents).all(), 'GL 금액이 변환 과정에서 바뀌었습니다.')
        mask = glt0['BUKRS (Company Code)'].eq(COMPANY) & glt0['RYEAR (Fiscal Year)'].eq(YEAR) & glt0['RLDNR (Ledger)'].eq(LEDGER) & glt0['RRCTY (Record Type)'].eq(RECORD_TYPE) & glt0['RVERS (Version)'].eq(VERSION)
        t = glt0.loc[mask].copy()
        require(not t.empty, '선택 범위에 TB 데이터가 없습니다. 설정값을 확인하세요.')
        require(t['RACCT (Account Number)'].notna().all(), 'TB 계정번호가 비어 있습니다.')
        base = pd.DataFrame({'GL_Account_Number': t['RACCT (Account Number)'], 'Business_Unit_Code': t['BUKRS (Company Code)'] + ':' + t['RBUSA (Business Area)'].fillna(''), 'Opening': cents(t['HSLVT (Balance carried forward in local currency (currency 2))'])})
        for n in range(1, 17):
            base[f'P{n:02d}'] = cents(t[f'HSL{n:02d} (Total transactions in the period in local currency (curr 2))'])
        group_keys = ['GL_Account_Number', 'Business_Unit_Code']
        aggregated = base.groupby(group_keys, dropna=False).sum().reset_index()
        opening = aggregated['Opening'].copy()
        tb_parts = []
        movement_parts = []
        for n in range(1, 17):
            change = aggregated[f'P{n:02d}']
            ending = opening + change
            month = min(n, 12)
            asof = f'{YEAR}{month:02d}{calendar.monthrange(int(YEAR), month)[1]:02d}'
            part = aggregated[group_keys].copy()
            part['Balance_AsOf_Date'] = asof
            part['Fiscal_Year'] = YEAR
            part['Period'] = f'{n:02d}'
            part['Amount_Beginning'] = opening / 100
            part['Amount_Currency'] = currency.iloc[0]
            part['Amount_Ending'] = ending / 100
            tb_parts.append(part)
            change_part = part[group_keys + ['Fiscal_Year', 'Period']].copy()
            change_part['TB_Movement_Cents'] = change
            movement_parts.append(change_part)
            opening = ending
        tb = pd.concat(tb_parts, ignore_index=True)
        tb_movements = pd.concat(movement_parts, ignore_index=True)
        require(not tb.duplicated(group_keys + ['Fiscal_Year', 'Period']).any(), 'TB 결과 키가 중복됩니다.')
        work = gl.copy()
        work['Net_Cents'] = signed_cents
        journal_balance = work.groupby(['Journal_ID', 'Amount_Currency'])['Net_Cents'].sum().reset_index()
        nonbalancing = journal_balance.loc[journal_balance['Net_Cents'].ne(0)].copy()
        recon_keys = ['GL_Account_Number', 'Business_Unit_Code', 'Fiscal_Year', 'Period']
        gl_movements = work.groupby(recon_keys)['Net_Cents'].sum().reset_index(name='GL_Movement_Cents')
        reconciliation = gl_movements.merge(tb_movements, on=recon_keys, how='outer', indicator=True)
        reconciliation[['GL_Movement_Cents', 'TB_Movement_Cents']] = reconciliation[['GL_Movement_Cents', 'TB_Movement_Cents']].fillna(0).astype('int64')
        reconciliation['Difference_Cents'] = reconciliation['GL_Movement_Cents'] - reconciliation['TB_Movement_Cents']
        reconciliation['GL_Movement'] = reconciliation['GL_Movement_Cents'] / 100
        reconciliation['TB_Movement'] = reconciliation['TB_Movement_Cents'] / 100
        reconciliation['Difference'] = reconciliation['Difference_Cents'] / 100
        reconciliation['Match_Status'] = reconciliation.pop('_merge')
        missing_data = gl.isna().sum().rename_axis('Field').reset_index(name='Missing_Row_Count')
        summary = {'status': 'draft_requires_review', 'company': COMPANY, 'fiscal_year': YEAR, 'ledger': LEDGER, 'record_type': RECORD_TYPE, 'version': VERSION, 'gl_input_rows': len(b), 'gl_output_rows': len(gl), 'tb_selected_input_rows': len(t), 'tb_output_rows': len(tb), 'unmatched_detail_rows': len(unmatched), 'duplicate_header_rows': len(duplicates), 'gl_amount_preserved': True, 'currency': str(currency.iloc[0]), 'debit_amount': int(amount_cents.loc[indicator.eq('D')].sum()) / 100, 'credit_amount': int(amount_cents.loc[indicator.eq('C')].sum()) / 100, 'nonbalancing_journal_count': len(nonbalancing), 'reconciliation_difference_rows': int(reconciliation['Difference_Cents'].ne(0).sum()), 'effective_date_min': gl['Effective_Date'].min(), 'effective_date_max': gl['Effective_Date'].max(), 'review_required': ['DMBTR/HWAER가 기능통화 기준인지 확인', 'GLT0 HSL이 동일한 통화 기준인지 확인', '회사·사업영역 조합이 감사 단위와 일치하는지 확인', '원장·실적구분·버전 및 달력연도 가정 확인', 'Source와 BLART의 의미 대응 및 Source_Listing 확보', 'Reversal_Indicator 코드 매핑 미완료', '계정과목표 미확보', 'Level 1 미확보 필드와 공란 사유 문서화', 'Base Standard의 전체 파일 표현 규칙 미검증']}
    except ValueError:
        fail('SAP_CONVERSION_FAILED','SAP','SAP 변환 조건·날짜·통화·금액 및 결합 키를 확인하세요.',table='SAP')
    supplement=pd.DataFrame({'Journal_ID':gl['Journal_ID'],'Journal_ID_Line_Number':gl['Journal_ID_Line_Number'],'Document_Date':m['BLDAT (Document Date in Document)'],'Entered_Time_SAP':m['CPUTM (Time of Entry)']})
    header_rows=h[keys+['__source_row']].rename(columns={'__source_row':'BKPF_Source_Row'})
    lineage=b[keys+['BUZEI (Number of Line Item Within Accounting Document)','__source_row']].merge(header_rows,on=keys,how='left',validate='many_to_one')
    lineage=pd.DataFrame({'Journal_ID':gl['Journal_ID'],'Journal_ID_Line_Number':gl['Journal_ID_Line_Number'],'BSEG_Source_Row':lineage['__source_row'],'BKPF_Source_Row':lineage['BKPF_Source_Row']})
    summary['input_row_count']=len(bseg)+len(bkpf)+len(glt0)
    summary['transaction_row_count']=len(gl)
    summary['issue_count']=int(summary['nonbalancing_journal_count'])+int(summary['reconciliation_difference_rows'])
    return AnalysisResult('sap_preprocessing',summary,{'gl':gl,'tb':tb,'nonbalancing_journals':nonbalancing,'gl_tb_reconciliation':reconciliation,'missing_fields':missing_data,'sap_supplement':supplement,'sap_lineage':lineage},{'assumptions':summary['review_required'],'limitation':'달력연도·소수 2자리 기준. SAP 필드명이 예제와 일치해야 하며 기능통화·원장 범위는 사용자가 확인해야 합니다. 변환은 감사 결론이 아닙니다.'})
