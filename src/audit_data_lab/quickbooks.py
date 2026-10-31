"""기존 ADS 예제의 5계정표시열+8거래열 QuickBooks 보고서 평탄화. ADS 변환 아님."""
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import re
import pandas as pd
from .common import AnalysisResult,fail

REPORT_FIELDS=['Type','Date','Num','Name','Memo','Split','Amount','Balance']
DATE_FORMATS={'%Y-%m-%d','%m/%d/%Y','%d/%m/%Y','%Y%m%d'}


def reshape_quickbooks_report(raw,*,date_format='%Y-%m-%d'):
    """header=None로 읽은 표. 첫 행은 앞5칸+정확한 REPORT_FIELDS 헤더여야 한다."""
    if not isinstance(date_format,str) or date_format not in DATE_FORMATS:fail('UNSUPPORTED_DATE_FORMAT','date_format','지원하는 날짜 형식을 명시하세요.',table='QuickBooks')
    if raw.empty:fail('EMPTY_INPUT','*','QuickBooks 보고서가 비어 있습니다.',table='QuickBooks')
    if len(raw.columns)!=13:fail('UNSUPPORTED_QUICKBOOKS_LAYOUT','Columns','계정 표시 5열과 거래 8열인 예제 형식만 지원합니다.',table='QuickBooks')
    def empty(value):return pd.isna(value) or (isinstance(value,str) and not value.strip())
    def label(value):return '' if empty(value) else str(value).strip()
    if [label(v) for v in raw.iloc[0,5:].tolist()]!=REPORT_FIELDS:
        fail('QUICKBOOKS_HEADER_MISMATCH','Header','첫 행의 6~13열은 Type, Date, Num, Name, Memo, Split, Amount, Balance여야 합니다. 제목 행·지역별 보고서 형식을 확인하세요.',table='QuickBooks',row=1)
    def parse_amount(value):
        text=label(value)
        if not text:return None
        negative=text.startswith('(') and text.endswith(')')
        if negative:text=text[1:-1]
        if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?',text):raise ValueError
        if negative and text.startswith('-'):raise ValueError
        n=Decimal(text.replace(',',''))
        if negative:n=-n
        if not n.is_finite() or abs(n)>Decimal('90000000000000'):raise ValueError
        return format(n,'f')
    account=None;account_source=None;output=[];dispositions=[{'QuickBooks_Source_Row':1,'Row_Type':'header','Reason':'지원 헤더 확인'}];issues=[]
    for pos in range(1,len(raw)):
        values=raw.iloc[pos].tolist();number=pos+1;head=[label(v) for v in values[:5] if not empty(v)]
        transaction=dict(zip(REPORT_FIELDS,values[5:]));kind='unsupported';reason='행 유형 또는 계정 연결을 확인할 수 없음'
        def issue(code,field,message):issues.append({'code':code,'field':field,'source_file':'QuickBooks','source_row':number,'message':message,'suggested_review':'원본 보고서와 지원 레이아웃·날짜 형식을 확인하세요.'})
        if all(empty(v) for v in values):kind='blank';reason='빈 행, 거래로 사용하지 않음'
        elif not empty(transaction['Date']):
            kind='transaction_rejected';reason='거래 후보 입력 검증 실패'
            before=len(issues)
            if len(head)>1:issue('AMBIGUOUS_ACCOUNT_HEADING','Account Description','한 행에 계정 표시가 여러 개 있습니다.');account=None;account_source=None
            elif head:account=head[0];account_source=number
            if account is None:issue('QUICKBOOKS_ACCOUNT_MISSING','Account Description','거래에 연결할 계정 표제가 없습니다.')
            if empty(transaction['Type']):issue('QUICKBOOKS_TYPE_MISSING','Type','거래 유형이 없습니다.')
            original=transaction['Date'];parsed=None
            try:
                if isinstance(original,(datetime,date,pd.Timestamp)):
                    if isinstance(original,datetime) and (original.hour or original.minute or original.second):raise ValueError
                    parsed=original.strftime('%Y-%m-%d')
                else:parsed=datetime.strptime(label(original),date_format).strftime('%Y-%m-%d')
            except (ValueError,TypeError,OverflowError):issue('INVALID_DATE','Date','날짜가 지정한 형식과 다릅니다. Excel 일련번호를 날짜로 추정하지 않습니다.')
            amount=None;balance=None
            for field in ['Amount','Balance']:
                try:
                    value=parse_amount(transaction[field])
                    if field=='Amount':amount=value
                    else:balance=value
                    if field=='Amount' and value is None:raise ValueError
                except (ValueError,InvalidOperation):issue('INVALID_AMOUNT',field,'금액 형식이 불명확합니다. 쉼표 천 단위·괄호 음수·소수 둘째 자리까지 지원합니다.')
            if len(issues)==before:
                row={k:(None if empty(v) else v) for k,v in transaction.items()}
                row.update({'Account Description':account,'Date':parsed,'Amount':amount,'Balance':balance,'QuickBooks_Source_Row':number,'Account_Source_Row':account_source})
                output.append(row);kind='transaction';reason='계정 표제와 날짜·금액을 확인한 거래행'
        else:
            words=[label(v) for v in values if not empty(v)];first=words[0] if words else ''
            has_numbers=not empty(transaction['Amount']) or not empty(transaction['Balance'])
            if re.match(r'^total\b',first,re.I) and has_numbers:
                kind='total';reason='보고서 합계 행: 중복 집계 방지를 위해 거래 출력에서 제외';account=None;account_source=None
            elif first.casefold() in {'beginning balance','opening balance'} and has_numbers:
                kind='opening_balance';reason='기초잔액 표시는 거래 출력에서 제외하고 원본 보존'
            elif len(head)==1 and all(empty(v) for v in values[5:]):
                account=head[0];account_source=number;kind='account_heading';reason='이후 거래행에 연결할 계정 표제'
            else:
                issue('UNCLASSIFIED_QUICKBOOKS_ROW','Row','날짜 없는 행의 의미를 확인할 수 없습니다. 자동 삭제하지 않고 원본 행 검토에 남깁니다.')
                account=None;account_source=None  # 모호한 경계를 넘어 앞 계정으로 채우지 않는다.
        dispositions.append({'QuickBooks_Source_Row':number,'Row_Type':kind,'Reason':reason})
    flat=pd.DataFrame(output,columns=['QuickBooks_Source_Row','Account_Source_Row','Account Description',*REPORT_FIELDS])
    classified=pd.DataFrame(dispositions);review_numbers=set(classified.loc[classified.Row_Type.isin(['unsupported','transaction_rejected']),'QuickBooks_Source_Row'])
    original=raw.copy();original.columns=[f'Column_{n+1}' for n in range(13)];original.insert(0,'QuickBooks_Source_Row',range(1,len(raw)+1))
    complete=not issues and bool(output)
    if not output:issues.append({'code':'NO_QUICKBOOKS_TRANSACTIONS','field':'*','source_file':'QuickBooks','source_row':None,'message':'변환할 수 있는 거래행이 없습니다.','suggested_review':'보고서 종류·헤더·계정 표제를 확인하세요.'})
    flat['Conversion_Status']='completed_flattening' if complete else 'incomplete_review_required'
    flat['ADS_Status']='not_converted'
    return AnalysisResult('quickbooks_preprocessing',{'input_report_row_count':len(raw),'transaction_row_count':len(flat),
        'review_row_count':len(review_numbers),'excluded_nontransaction_row_count':int(classified.Row_Type.isin(['header','blank','account_heading','total','opening_balance']).sum()),
        'conversion_status':'completed_flattening' if complete else 'incomplete_review_required','ads_status':'not_converted'},
        {'modified_gl':flat,'row_dispositions':classified,'review_rows':original.loc[original.QuickBooks_Source_Row.isin(review_numbers)].copy(),
         'module_issues':pd.DataFrame(issues,columns=['code','field','source_file','source_row','message','suggested_review'])},
        {'date_format':date_format,'supported_layout':'앞 5개 계정 표시 열 + Type/Date/Num/Name/Memo/Split/Amount/Balance',
         'scope':'QuickBooks 예제 보고서 평탄화입니다. 거래 ID·계정 코드·통화·입력 사용자·입력일·회계기간을 추정하지 않습니다.',
         'limitation':'ADS GL이 아닙니다. Num의 유일성·전표 완전성·기초잔액 대사·합계 산술 검증은 수행하지 않았습니다. 미분류·거부 행이 있으면 modified_gl은 부분 결과입니다.',
         'excluded_row_policy':'표제·빈 행·기초잔액·합계 행은 유형과 원본 위치를 기록합니다. 합계 값으로 거래 금액을 대체하지 않습니다.'})
