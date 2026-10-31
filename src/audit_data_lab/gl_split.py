"""GL 행을 입력 사용자별로 분할. 한 전표가 여러 사용자 행으로 구성되면 나뉠 수 있다."""
import pandas as pd
from .common import AnalysisResult,columns,fail


def split_gl_by_user(gl,*,user_column='Entered_By',max_groups=500):
    if not isinstance(user_column,str) or not user_column.strip():fail('INVALID_PARAMETER','user_column','사용자 컬럼명을 지정하세요.',table='GL')
    if isinstance(max_groups,bool) or not isinstance(max_groups,int) or not 1<=max_groups<=2000:fail('INVALID_PARAMETER','max_groups','분할 파일 한도는 1~2000의 정수여야 합니다.',table='GL')
    columns(gl,[user_column],'GL')
    if gl.empty:fail('EMPTY_INPUT','*','분할할 GL 행이 없습니다.',table='GL')
    if 'Split_Source_Row' in gl:fail('RESERVED_COLUMN','Split_Source_Row','분할 추적용 컬럼이 이미 있습니다. 이전 분할 결과인지 확인하세요.',table='GL')
    values=gl[user_column].astype('string')
    missing=values.isna()|values.str.strip().eq('')
    # 사용자명이 같아 보여도 공백·대소문자를 임의 정규화하여 합치지 않는다.
    keys=values.mask(missing,pd.NA)
    group_count=keys.nunique(dropna=True)+int(missing.any())
    if group_count>max_groups:fail('SPLIT_GROUP_LIMIT',user_column,'분할 파일 한도를 초과했습니다. 범위를 줄이거나 한도를 확인하세요.',table='GL')
    tables={};index=[];issues=[];membership=[]
    grouped=gl.groupby(keys,sort=False,dropna=False).indices
    for number,(key,positions) in enumerate(grouped.items(),start=1):
        unassigned=pd.isna(key)
        positions=list(positions)
        name=f'user_{number:04d}' if not unassigned else 'unassigned_user'
        frame=gl.iloc[positions].copy()
        frame.insert(0,'Split_Source_Row',[pos+2 for pos in positions])
        tables[name]=frame
        index.append({'Group_ID':name,'Entered_By':None if unassigned else str(key),'User_Column':user_column,
            'User_Status':'missing_user' if unassigned else 'provided','Row_Count':len(frame),'Output_File':name+'.csv'})
        for pos in positions:
            membership.append({'Group_ID':name,'Source_Row':pos+2})
            if unassigned:issues.append({'code':'MISSING_ENTERED_BY','field':user_column,'source_file':'GL','source_row':pos+2,
                'message':'입력 사용자 미확보: 삭제하지 않고 unassigned_user.csv로 분리했습니다.','suggested_review':'추출 범위와 입력 사용자 원본 필드를 확인하세요.'})
    index_frame=pd.DataFrame(index)
    tables={'group_index':index_frame,'row_membership':pd.DataFrame(membership),**tables,
        'module_issues':pd.DataFrame(issues,columns=['code','field','source_file','source_row','message','suggested_review'])}
    return AnalysisResult('gl_user_split',{'input_row_count':len(gl),'exported_row_count':sum(index_frame.Row_Count),
        'user_group_count':int(keys.nunique(dropna=True)),'output_file_count':len(index),'missing_user_row_count':int(missing.sum())},tables,
        {'user_column':user_column,'max_groups':max_groups,'row_number_basis':'헤더 1행, 첫 논리 데이터 행 2. CSV 물리 줄 번호와 다를 수 있습니다.',
         'split_policy':'사용자 문자열을 그대로 구분합니다. 빈 값·공백만 있는 값은 미확보 그룹에 보관하며 원본 값은 수정하지 않습니다.',
         'limitation':'입력 사용자별 GL 행 분할입니다. 전표 전체를 한 파일에 보관하는 기능이 아니며 다중 사용자 전표는 여러 파일에 걸칠 수 있습니다. 분할 파일 하나만으로 차대변 균형을 판단하지 마세요.',
         'download_policy':'사용자명을 파일 경로로 사용하지 않습니다. CSV 수식 방지 이스케이프가 적용됩니다. CSV는 계정·사용자 코드의 Excel 자동 형변환을 제어하지 못하므로 텍스트로 가져오세요.'})
