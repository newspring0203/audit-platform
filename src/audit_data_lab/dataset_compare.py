"""버전 간 원본 문자열 비교. 명시적 유일 키만 사용하고 금액 의미를 추정하지 않는다."""
from .common import columns,fail

def compare_datasets(prior,current,keys):
    if not keys or len(keys)>12 or len(set(keys))!=len(keys):fail('COMPARISON_KEY_REQUIRED','keys','1~12개의 중복 없는 비교 키를 지정하세요.',table='Comparison')
    for name,frame in [('Prior',prior),('Current',current)]:
        columns(frame,keys,name)
        missing=frame[keys].isna().any(axis=1)|frame[keys].astype('string').apply(lambda x:x.str.strip().eq('')).any(axis=1)
        if missing.any():fail('COMPARISON_KEY_MISSING','keys','비교 키에 빈 값이 있습니다.',table=name)
        if frame.duplicated(keys).any():fail('COMPARISON_KEY_DUPLICATED','keys','비교 키가 유일하지 않습니다. 회사·연도·전표행 등의 키를 추가하세요.',table=name)
    def index(frame):
        return {tuple(str(row[k]) for k in keys):(n+2,row.to_dict()) for n,(_,row) in enumerate(frame.iterrows())}
    before=index(prior);after=index(current);changes=[];counts={'added':0,'removed':0,'changed':0,'unchanged':0}
    fields=list(dict.fromkeys([*prior.columns,*current.columns]))
    def scalar(value):return None if value is None or __import__('pandas').isna(value) else str(value)
    for key in sorted(set(before)|set(after)):
        p=before.get(key);c=after.get(key)
        kind='added' if p is None else 'removed' if c is None else 'changed'
        diff=[field for field in fields if scalar(p[1].get(field) if p else None)!=scalar(c[1].get(field) if c else None)]
        if p and c and not diff:counts['unchanged']+=1;continue
        counts[kind]+=1
        changes.append({'kind':kind,'key':dict(zip(keys,key)),'prior_row':p[0] if p else None,'current_row':c[0] if c else None,
            'changed_fields':diff,'prior':{f:scalar(p[1].get(f)) for f in diff} if p else None,'current':{f:scalar(c[1].get(f)) for f in diff} if c else None})
    return {'summary':counts,'keys':keys,'columns_added':[f for f in current if f not in prior],'columns_removed':[f for f in prior if f not in current],
        'changes':changes,'policy':'원본 문자열 기준 비교입니다. 행 순서로 연결하지 않습니다. 100과 100.00 등 표현 차이도 변경이며 회계 오류를 뜻하지 않습니다.'}
