"""원본을 삭제하거나 덮어쓰지 않는 데이터 품질 프로파일."""
import pandas as pd
from .common import AnalysisResult, columns, money
from .validation import DataValidationError


def profile_data(frame, *, required_columns=(), date_columns=(), amount_columns=()):
    columns(frame,[])
    required_columns=tuple(dict.fromkeys([*required_columns,*date_columns,*amount_columns]))
    table=[];issues=[]
    for c in frame:
        values=frame[c].astype('string')
        missing=values.isna()|values.str.strip().eq('')
        table.append({'Field':c,'Row_Count':len(frame),'Missing_Count':int(missing.sum()),'Unique_Count':int(values.nunique(dropna=True))})
        if c in required_columns:
            for pos in range(len(frame)):
                if missing.iloc[pos]:issues.append({'Code':'MISSING_VALUE','Field':c,'Source_Row':pos+2,'Value':None,'Message':'필수 값이 비어 있습니다.'})
    for c in required_columns:
        if c not in frame:issues.append({'Code':'MISSING_COLUMN','Field':c,'Source_Row':None,'Value':None,'Message':'필요한 컬럼이 없습니다.'})
    for c in date_columns:
        if c not in frame:continue
        values=frame[c].astype('string')
        bad=~values.str.fullmatch(r'\d{8}').fillna(False)|pd.to_datetime(values,format='%Y%m%d',errors='coerce').isna()
        for pos in range(len(frame)):
            if bad.iloc[pos]:issues.append({'Code':'INVALID_DATE','Field':c,'Source_Row':pos+2,'Value':None if pd.isna(values.iloc[pos]) else str(values.iloc[pos]),'Message':'YYYYMMDD 날짜를 확인하세요.'})
    for c in amount_columns:
        if c not in frame:continue
        try:money(frame[c],c)
        except DataValidationError as error:
            for i in error.issues:issues.append({'Code':i.code,'Field':i.field,'Source_Row':i.source_row,'Value':i.value,'Message':i.message})
    problems=pd.DataFrame(issues,columns=['Code','Field','Source_Row','Value','Message'])
    duplicates=frame.loc[frame.duplicated(keep=False)].copy()
    return AnalysisResult('data_cleansing',{'row_count':len(frame),'column_count':len(frame.columns),
        'issue_count':len(problems),'duplicate_row_count':len(duplicates)},
        {'field_profile':pd.DataFrame(table),'issues':problems,'duplicate_rows':duplicates},
        {'policy':'검사만 수행합니다. 중복·결측 행을 임의로 삭제하거나 금액을 0으로 바꾸지 않습니다.',
         'sap_conversion':'SAP–ADS 변환은 reshape_rename_sap_data.ipynb, SAP 오류 검사는 validation.py를 사용합니다.'})
