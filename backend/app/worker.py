"""분석 자식 프로세스 진입점."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from audit_data_lab import execute_analysis, generate_working_paper, export_review_excel
from backend.app.analysis_dispatch import AnalysisContext, run_analysis
from backend.app.input_data import JobInputs
from backend.app.reporting import write_job_report


def run(spec, *, dart_api_key=None):
    inputs = JobInputs(spec)
    context = AnalysisContext(spec, inputs, dart_api_key=dart_api_key)
    result = execute_analysis(
        context.module,
        lambda: run_analysis(context),
        context={"request_id": spec["job_id"]},
    )
    write_job_report(
        spec, result, inputs,
        paper_writer=generate_working_paper,
        excel_writer=export_review_excel,
    )


if __name__ == "__main__":
    try:
        run(json.loads(Path(sys.argv[1]).read_text()), dart_api_key=sys.stdin.read(41) or None)
    except Exception:
        # 원본·키·상세 예외를 프로세스 출력에 남기지 않는다.
        raise SystemExit(2)
