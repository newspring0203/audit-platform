"""분석 결과·입력 오류의 공통 형식. 웹 프레임워크에 의존하지 않는다."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import pandas as pd
from .validation import DataValidationError, ValidationIssue
from .result import AnalysisResult


def fail(code, field, message, *, table='input', row=None, value=None):
    raise DataValidationError([ValidationIssue(code=code, field=field, message=message,
        source_table=table, source_file=table, source_row=row,
        source_field=field, value=None if value is None or pd.isna(value) else str(value))])


def columns(frame, names, table='input'):
    if frame.columns.duplicated().any():
        fail('DUPLICATE_COLUMNS','*','컬럼명이 중복됩니다.',table=table)
    missing=[n for n in names if n not in frame]
    if missing:
        raise DataValidationError([ValidationIssue(code='MISSING_COLUMN',field=n,
            message=f'필요한 컬럼이 없습니다: {n}',source_table=table,source_file=table,source_field=n)
            for n in missing])


def text(frame, column, table='input'):
    values=frame[column].astype('string').str.strip()
    invalid=values.isna() | values.eq('')
    if invalid.any():
        pos=next(i for i,v in enumerate(invalid) if v)
        fail('MISSING_VALUE',column,'빈 값이 있습니다.',table=table,row=pos+2)
    return values


def money(values, field='Amount', table='input'):
    results=[];issues=[]
    for pos,value in enumerate(values):
        try:
            n=Decimal(str(value))
            if not n.is_finite() or n*100 != (n*100).to_integral_value() or abs(n*100)>9_000_000_000_000_000:
                raise InvalidOperation
            results.append(int(n*100))
        except (InvalidOperation,ValueError,TypeError):
            results.append(0)
            issues.append(ValidationIssue(code='INVALID_AMOUNT',field=field,
                message='금액은 소수 둘째 자리까지의 유한한 숫자여야 합니다.',source_table=table,
                source_file=table,source_row=pos+2,source_field=field,
                value=None if pd.isna(value) else str(value)))
    if issues:raise DataValidationError(issues)
    return pd.Series(results,index=values.index,dtype='int64')


def date_values(values, field, table='input'):
    values=values.astype('string')
    parsed=pd.to_datetime(values,format='%Y%m%d',errors='coerce')
    bad=~values.str.fullmatch(r'\d{8}').fillna(False) | parsed.isna()
    if bad.any():
        pos=next(i for i,v in enumerate(bad) if v)
        fail('INVALID_DATE',field,'날짜는 YYYYMMDD 형식이어야 합니다.',table=table,row=pos+2,value=values.iloc[pos])
    return parsed


def prepare_gl(gl):
    required=['Journal_ID','GL_Account_Number','Business_Unit_Code','Fiscal_Year','Period',
        'Amount','Amount_Currency','Amount_Credit_Debit_Indicator','Effective_Date','Entered_Date','Entered_By']
    columns(gl,required,'GL')
    if gl.empty:fail('EMPTY_INPUT','*','GL 데이터가 없습니다.',table='GL')
    g=gl.copy().reset_index(drop=True)
    for c in required:
        if c not in ['Amount']:g[c]=text(g,c,'GL')
    bad=~g['Amount_Credit_Debit_Indicator'].isin(['D','C'])
    if bad.any():fail('INVALID_DC_CODE','Amount_Credit_Debit_Indicator','ADS의 D/C 코드가 필요합니다.',table='GL',row=int(bad[bad].index[0])+2)
    if not g['Amount_Currency'].str.fullmatch(r'[A-Z]{3}').all():
        fail('INVALID_CURRENCY','Amount_Currency','통화는 영문 대문자 3자리여야 합니다.',table='GL')
    for c in ['Effective_Date','Entered_Date']:
        date_values(g[c],c,'GL')
    valid_period=g['Period'].str.fullmatch(r'\d{1,2}') & pd.to_numeric(g['Period'],errors='coerce').between(1,16)
    if not valid_period.all():fail('INVALID_PERIOD','Period','회계기간은 정수 1~16이어야 합니다.',table='GL')
    if not g['Fiscal_Year'].str.fullmatch(r'\d{4}').all():fail('INVALID_YEAR','Fiscal_Year','회계연도는 4자리여야 합니다.',table='GL')
    g['Period']=g['Period'].str.zfill(2)
    g['_amount_cents']=money(g['Amount'],'Amount','GL')
    g['_net_cents']=g['_amount_cents'].where(g['Amount_Credit_Debit_Indicator'].eq('D'),-g['_amount_cents'])
    g['_source_row']=range(2,len(g)+2)
    return g
