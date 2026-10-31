"""검토 가능한 컬럼 매핑 제안. 모호한 이름을 임의 선택하거나 ADS 준수를 인증하지 않는다."""
import json,unicodedata
import pandas as pd
from .common import AnalysisResult,columns,text

ALIASES={
 'Journal_ID':['BELNR','전표번호'],'Journal_ID_Line_Number':['BUZEI','전표행번호'],
 'GL_Account_Number':['HKONT','계정번호'],'Effective_Date':['BUDAT','전기일'],
 'Entered_Date':['CPUDT','입력일'],'Entered_Time':['CPUTM','입력시간'],'Entered_By':['USNAM','입력자'],
 'Fiscal_Year':['GJAHR','회계연도'],'Period':['MONAT','회계기간'],
 'Amount':['DMBTR'],'Amount_Currency':['HWAER'],
 'Amount_Credit_Debit_Indicator':['SHKZG'],'JE_Header_Description':['BKTXT'],
 'JE_Line_Description':['SGTXT'],'Source':['BLART'],
}

def normalized(value):return unicodedata.normalize('NFKC',str(value)).split(' (',1)[0].strip().casefold()


def review_column_mapping(frame,mapping=None):
    columns(frame,[])
    suggestions=[];issues=[];mapped=None
    for target,aliases in ALIASES.items():
        accepted={normalized(c) for c in [target]+aliases}
        candidates=[c for c in frame.columns if normalized(c) in accepted]
        suggestions.append({'Target_Field':target,'Candidates':json.dumps(candidates,ensure_ascii=False),
            'Status':'candidate' if len(candidates)==1 else 'ambiguous' if candidates else 'not_found',
            'Suggested_Source':candidates[0] if len(candidates)==1 else None})
    status='suggestions_only'
    if mapping is not None:
        columns(mapping,['Target_Field','Source_Field'],'Mapping')
        m=mapping.copy()
        for c in ['Target_Field','Source_Field']:m[c]=text(m,c,'Mapping')
        for pos,(_,row) in enumerate(m.iterrows(),start=2):
            target,source=row['Target_Field'],row['Source_Field']
            code=None;message=None
            if target not in ALIASES:code='UNKNOWN_TARGET_FIELD';message='지원 대상 ADS 필드가 아닙니다.'
            elif source not in frame:code='SOURCE_COLUMN_MISSING';message='원본 컬럼이 없습니다.'
            elif m['Target_Field'].eq(target).sum()>1:code='DUPLICATE_TARGET_MAPPING';message='동일 대상 필드를 여러 번 지정했습니다.'
            elif m['Source_Field'].eq(source).sum()>1:code='DUPLICATE_SOURCE_MAPPING';message='한 원본 컬럼을 여러 의미로 사용하려면 별도 변환 정의가 필요합니다.'
            if code:issues.append({'code':code,'field':target,'source_row':pos,'source_file':'Mapping','message':message,'suggested_review':'원본 컬럼과 의미를 확인해 매핑표를 수정하세요.'})
        if not issues:
            rename=dict(zip(m.Source_Field,m.Target_Field))
            candidate=frame.rename(columns=rename)
            if candidate.columns.duplicated().any():issues.append({'code':'MAPPING_COLUMN_COLLISION','field':'Mapping','source_file':'Mapping','message':'매핑 후 기존 컬럼과 이름이 충돌합니다.','suggested_review':'기존 대상 컬럼과 원본 컬럼 중 사용할 필드를 확인하세요.'})
            else:mapped=candidate.copy();status='column_names_mapped'
        if issues:status='not_applied_mapping_issue'
    return status,pd.DataFrame(suggestions),pd.DataFrame(issues),mapped


def cleanse_data(frame,*,mapping=None,required_columns=(),date_columns=(),amount_columns=()):
    from .cleansing import profile_data
    status,suggestions,issues,mapped=review_column_mapping(frame,mapping)
    result=profile_data(mapped if mapped is not None else frame,required_columns=required_columns,date_columns=date_columns,amount_columns=amount_columns)
    result.tables.update({'mapping_suggestions':suggestions,'module_issues':issues})
    if mapped is not None:result.tables['mapped_data']=mapped
    result.summary['mapping_status']=status;result.metadata['mapping_status']=status
    result.metadata['mapping_limit']='제안만으로 매핑을 적용하지 않습니다. 명시적 매핑표가 있어도 컬럼명만 변경하며 날짜·금액·통화·차대변 의미 변환 및 ADS 전체 검증은 별도입니다.'
    return result
