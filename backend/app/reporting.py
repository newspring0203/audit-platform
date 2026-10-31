"""분석 결과의 추적 정보·조서·다운로드 ZIP을 만든다."""
from pathlib import Path
import hashlib
import json
import zipfile
from audit_data_lab.traceability import attach_traceability, records

ROOT = Path(__file__).resolve().parents[2]


def write_job_report(spec, result, inputs, *, paper_writer, excel_writer):
    folder = Path(spec['directory'])
    parameters = spec['parameters']
    engine = hashlib.sha256()
    for code in sorted((ROOT / 'src' / 'audit_data_lab').glob('*.py')):
        engine.update(code.name.encode())
        engine.update(code.read_bytes())
    result.metadata['engine_sha256'] = engine.hexdigest()
    manifest = attach_traceability(result, inputs.frames, inputs.sources, run_id=spec['job_id'], parameters=parameters)
    paper_dir = folder / 'report'
    paper_writer(result, paper_dir, entity='사용자 제출 자료', period='입력 조건 참조', prepared_by='검토자 미지정')
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / 'review_snapshot.json').write_text(json.dumps(manifest, ensure_ascii=False, allow_nan=False))
    (folder / 'source_rows.json').write_text(json.dumps({slot: records(frame) for slot, frame in inputs.frames.items()}, ensure_ascii=False, allow_nan=False))
    if spec.get('excel_node') and spec.get('excel_modules'):
        try:
            excel_writer(result, paper_dir / 'review.xlsx', entity='사용자 제출 자료', period='입력 조건 참조', node_executable=spec['excel_node'], artifact_modules=spec['excel_modules'])
        except Exception:
            (paper_dir / 'excel_export_issue.json').write_text(json.dumps({'code': 'EXCEL_EXPORT_FAILED', 'message': 'Excel 생성에 실패했으나 CSV·Markdown 검토 결과를 제공합니다.'}, ensure_ascii=False))
    with zipfile.ZipFile(folder / 'bundle.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for file in paper_dir.rglob('*'):
            if file.is_file() and (not file.name.startswith('_')) and ('.inspect.' not in file.name):
                z.write(file, 'review/' + str(file.relative_to(paper_dir)))
    (folder / 'completion.json').write_text(json.dumps({'execution_status': result.metadata['execution_status']}))
