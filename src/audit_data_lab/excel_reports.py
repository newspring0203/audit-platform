"""검토 결과를 Excel로 내보내는 Python 진입점. JS Artifact Tool 렌더러를 호출한다."""
import json,math,os,shutil,subprocess,tempfile
from pathlib import Path
import pandas as pd
from .common import fail
from .review_service import NEXT_ACTIONS

STATUS_LABELS={'completed':'수행 완료','completed_with_limitations':'일부 검사 미실행',
    'not_executed_input_issue':'입력 문제로 계산 미실행','not_executed_system_issue':'처리 문제로 계산 미실행',
    'basis_information_missing':'기준 정보 미확보로 대사 미실행','basis_not_comparable':'비교 기준 불일치로 대사 미실행',
    'basis_evidence_invalid':'근거 재확인 필요로 대사 미실행','matched':'대사 수행 후 차이 없음','differences_found':'대사 수행 후 차이 있음'}
RULE_LABELS={'UNBALANCED_JOURNAL':'전표 차대변 균형','REPEATED_ACCOUNT_AMOUNT':'계정·금액 반복','ROUND_AMOUNT':'정액 거래',
    'WEEKEND_ENTRY':'주말 입력','NIGHT_ENTRY':'야간 입력','RARE_USER':'저빈도 사용자','RARE_ACCOUNT':'저빈도 계정',
    'LARGE_AMOUNT':'고액 거래','CLOSING_MANUAL':'결산일 수동 출처','DOCUMENT_AFTER_ENTRY':'문서일·입력일 비교'}


def build_review_payload(result,*,entity,period,source_labels=()):
    summary=result.summary;metadata=result.metadata
    checks=[]
    for rule,counts in summary.get('rules',{}).items():
        checks.append([RULE_LABELS.get(rule,rule),'수행',counts['row_count'],counts['journal_count'],''])
    for item in metadata.get('skipped_rules',[]):
        checks.append([RULE_LABELS.get(item['rule'],item['rule']),'미실행',None,None,item['reason']])
    if result.name=='jet':
        checks.append(['GL·로그 금액 대사',STATUS_LABELS.get(summary.get('log_amount_reconciliation_status'), '미실행'),
            summary.get('log_control_exception_count'),None,'대사 기준 확인 결과에 따라 수행 여부를 구분'])
    issues=[]
    for name in ['validation_issues','log_basis_issues','module_issues']:
        if name in result.tables:
            for _,row in result.tables[name].iterrows():
                value=row.get('value')
                issues.append({'오류 코드':row.get('code'),'필드':row.get('field'),
                    '원본 파일':row.get('source_file'),'원본 행':row.get('source_row'),
                    '입력값':None if pd.isna(value) else value,'원인':row.get('message'),
                    '후속 검토':row.get('suggested_review',NEXT_ACTIONS.get(row.get('code'),'원본과 검사 조건 확인')),
                    '검토 상태':'미검토','검토 의견':'','근거':'','검토자':'','검토일':None})
    primary=None;primary_name=None
    for name in ['flagged_lines','review_items','modified_gl','group_index','year_comparison','unmatched_bank','insights','issues']:
        if name in result.tables:
            primary=result.tables[name].copy();primary_name=name;break
    if primary is None:primary=pd.DataFrame()
    if primary_name=='flagged_lines':
        selected=['Journal_ID','Journal_ID_Line_Number','Source_Row','GL_Account_Number','Amount','Amount_Currency',
            'Effective_Date','Entered_Date','Rule_ID','Selection_Reason','Suggested_Review']
        primary=primary[[c for c in selected if c in primary]].copy()
        primary.insert(0,'Review_ID',[
            f"{row.get('Rule_ID','')}:{row.get('Journal_ID','')}:{row.get('Source_Row','')}" for _,row in primary.iterrows()])
        if 'Amount' in primary:primary['Amount']=pd.to_numeric(primary['Amount'],errors='raise')
    for c in ['검토 상태','검토 의견','근거','검토자','검토일']:
        primary[c]='미검토' if c=='검토 상태' else None
    tables={'검토대상':{'columns':list(primary.columns),'records':json.loads(primary.to_json(orient='records',date_format='iso',force_ascii=False))}}
    module_summary=[['검사 모듈',result.name],['결과 표 수',len(result.tables)],['확인 필요 사항',len(issues)],['주요 결과 행',len(primary)],['결과 상태',metadata.get('execution_status','completed')]]
    payload={'entity':entity,'period':period,'module':result.name,
        'execution_status':STATUS_LABELS.get(metadata.get('execution_status', 'completed_with_limitations' if summary.get('log_amount_reconciliation_status','').startswith('basis_') else 'completed'),'처리 상태 확인 필요'),
        'summary':module_summary if result.name!='jet' else [
            ['입력 상세행',summary.get('input_row_count')],['입력 전표',summary.get('journal_count')],
            ['검토 후보 전표',summary.get('flagged_journal_count')],
            ['로그 금액 대사',STATUS_LABELS.get(summary.get('log_amount_reconciliation_status'),'해당 없음')],
            ['로그 금액 차이 그룹',summary.get('log_control_exception_count')],
        ],'checks':checks,'issues':issues,'tables':tables,
        'conditions':{'source_files':list(source_labels),'config':metadata.get('config',{}),'input_fingerprints':metadata.get('input_fingerprints',{}),
            'basis_status':metadata.get('log_basis_status','not_applicable'),
            'basis_confirmation':metadata.get('log_basis_confirmation',{}),
            'scope':metadata.get('analysis_scope',metadata.get('limitation','')),
            'standards':'AICPA ADS GL July 2015 구조 및 감사증거 평가 원칙을 참고. 전체 기준 준수 인증 아님.'}}
    def clean(value):
        if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [clean(v) for v in value]
        if value is None or isinstance(value,(str,bool,int)):return value
        if isinstance(value,float):return value if math.isfinite(value) else None
        if pd.isna(value):return None
        if hasattr(value,'item'):return clean(value.item())
        return str(value)
    return clean(payload)



def export_review_excel(result,path,*,entity,period,source_labels=(),node_executable=None,artifact_modules=None):
    node_executable=node_executable or os.environ.get('AUDIT_XLSX_NODE')
    artifact_modules=artifact_modules or os.environ.get('AUDIT_XLSX_MODULES')
    if not node_executable or not artifact_modules:
        fail('XLSX_RUNTIME_REQUIRED','Excel','Excel 렌더러 설정이 없습니다. CSV·Markdown 조서는 사용할 수 있습니다.',table='Export')
    target=Path(path).resolve()
    if target.exists():raise FileExistsError('기존 검토 Excel을 덮어쓰지 않도록 새 경로를 사용하세요.')
    payload=build_review_payload(result,entity=entity,period=period,source_labels=source_labels)
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);(folder/'node_modules').symlink_to(Path(artifact_modules),target_is_directory=True)
        shutil.copy2(Path(__file__).with_name('excel_report_writer.mjs'),folder/'writer.mjs')
        (folder/'payload.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        allowed_env={'PATH','HOME','LANG','LC_ALL','TZ','TMPDIR','TMP','TEMP','SSL_CERT_FILE','SSL_CERT_DIR'}
        renderer_env={k:v for k,v in os.environ.items() if k in allowed_env}
        process=subprocess.run([str(node_executable),str(folder/'writer.mjs'),str(folder/'payload.json'),str(target)],
            capture_output=True,text=True,timeout=180,check=False,env=renderer_env)
        if process.returncode:
            target.parent.mkdir(parents=True,exist_ok=True)
            diagnostic=target.parent/'_excel_export_diagnostics.log'
            fd=os.open(diagnostic,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as log:
                log.write((process.stdout+'\n'+process.stderr)[-10000:])
            fail('XLSX_EXPORT_FAILED','Excel','Excel 생성에 실패했습니다. CSV·Markdown 결과를 사용하고 실행 기록을 확인하세요.',table='Export')
    return target
