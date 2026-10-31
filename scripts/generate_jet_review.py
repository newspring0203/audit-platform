"""입력 문제가 있어도 원인·후속 검토가 담긴 조서와 선택적 Excel을 생성한다."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import pandas as pd
from audit_data_lab import (adapt_legacy_log,run_jet,execute_analysis,generate_working_paper,export_review_excel,frame_fingerprint)
from audit_data_lab.validation import DataValidationError

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--gl',required=True);parser.add_argument('--log',required=True)
    parser.add_argument('--company',required=True);parser.add_argument('--year',required=True)
    parser.add_argument('--entity',required=True)
    parser.add_argument('--node');parser.add_argument('--modules')
    args=parser.parse_args()
    gl_path=Path(args.gl);log_path=Path(args.log)
    if not gl_path.is_absolute():gl_path=ROOT/gl_path
    if not log_path.is_absolute():log_path=ROOT/log_path
    def operation():
        gl=pd.read_csv(gl_path,dtype='string')
        raw_log=pd.read_csv(log_path,dtype='string')
        log=adapt_legacy_log(raw_log,company=args.company,fiscal_year=args.year)
        result=run_jet(gl,log,log_basis=None,evidence_root=ROOT/'data/evidence')
        result.metadata['input_fingerprints']={'gl':frame_fingerprint(gl),'log':frame_fingerprint(log)}
        return result
    result=execute_analysis('jet',operation,context={'company':args.company,'fiscal_year':args.year,
        'input_files':[gl_path.name,log_path.name]})
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder=ROOT/'outputs/reviews'/run_id
    generate_working_paper(result,folder,entity=args.entity,period=args.year,prepared_by='검토자 미지정')
    excel=None
    if args.node and args.modules:
        try:
            excel=export_review_excel(result,folder/'JET_review.xlsx',entity=args.entity,period=args.year,
                source_labels=[gl_path.name,log_path.name],node_executable=args.node,artifact_modules=args.modules)
        except DataValidationError as error:
            (folder/'excel_export_issue.json').write_text(json.dumps(error.to_dict(),ensure_ascii=False,indent=2))
    print(json.dumps({'execution_status':result.metadata['execution_status'],
        'log_amount_reconciliation_status':result.summary.get('log_amount_reconciliation_status'),
        'log_control_exception_count':result.summary.get('log_control_exception_count'),
        'report_directory':str(folder),'excel':str(excel) if excel else None},ensure_ascii=False,indent=2))
    return 0 if excel is not None or not args.node else 2

if __name__=='__main__':raise SystemExit(main())
