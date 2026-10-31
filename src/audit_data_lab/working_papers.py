"""분석 결과를 검토용 Markdown·CSV 조서 초안으로 묶는다."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from .common import AnalysisResult


def generate_working_paper(result: AnalysisResult, directory, *, entity, period, prepared_by):
    if not all(isinstance(v,str) and v.strip() for v in [entity,period,prepared_by]):
        raise ValueError('회사·기간·작성자를 입력하세요.')
    target=Path(directory)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError('기존 검토 기록을 덮어쓰지 않도록 새 조서 폴더를 사용하세요.')
    if not re.fullmatch(r'[a-z][a-z0-9_]*',result.name):raise ValueError('모듈 이름을 확인하세요.')
    result.save(target/'analysis')
    # 이스케이프하여 사용자 텍스트가 Markdown 구조를 바꾸지 않게 한다.
    def literal(value):return json.dumps(value,ensure_ascii=False)
    log_status=result.summary.get('log_amount_reconciliation_status')
    execution=result.metadata.get('execution_status','completed')
    warnings=[]
    if log_status and log_status.startswith('basis_'):
        warnings.append('> 로그 대사 미실행: 기준 정보 또는 근거가 확인되지 않았습니다. 차이 없음으로 해석하지 마세요.')
    if result.summary.get('conversion_status')=='incomplete_review_required':
        warnings.append('> 변환 미완료: modified_gl.csv는 부분 결과일 수 있습니다. 미분류·거부 행을 검토하기 전에는 전체 거래 모집단으로 사용하지 마세요.')
    if execution.startswith('not_executed'):
        warnings.append('> 계산 미실행: 입력 문제 또는 내부 처리 문제입니다. 아래 원인·후속 검토 목록을 확인하세요.')
    lines=warnings+['# 감사 지원 조서 초안','',f'- 회사: {literal(entity)}',f'- 기간: {literal(period)}',
           f'- 작성자: {literal(prepared_by)}',f'- 생성 시각(UTC): {datetime.now(timezone.utc).isoformat()}',
           f'- 분석 모듈: {result.name}','- 검토 상태: 미검토','',
           '## 수행 결과','', '```json',json.dumps(result.summary,ensure_ascii=False,indent=2,allow_nan=False),'```','',
           '## 분석 조건과 한계','', '```json',json.dumps(result.metadata,ensure_ascii=False,indent=2,allow_nan=False),'```','',
           '## 첨부 결과','']
    lines += [f'- [{name}.csv](analysis/{name}.csv)' for name in result.tables]
    lines += ['','## 감사인 후속 검토','','- 검토한 증빙:','- 추가 절차:','- 판단 근거:','- 검토자·검토일:',
              '','자동 생성된 초안입니다. 감사 결론이나 승인·서명을 자동으로 생성하지 않습니다.']
    (target/'working_paper.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return target/'working_paper.md'
