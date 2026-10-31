"""분석 결과의 추적 정보·조서·다운로드 ZIP을 만든다."""
from pathlib import Path
import gc
import hashlib
import json
import zipfile
from audit_data_lab.traceability import attach_traceability

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
    paper_dir.mkdir(parents=True, exist_ok=True)
    # Stream JSON instead of holding a second full Unicode copy of every record.
    with (paper_dir / 'review_snapshot.json').open('w', encoding='utf-8') as output:
        json.dump(manifest, output, ensure_ascii=False, allow_nan=False)
    del manifest
    gc.collect()
    with (folder / 'source_rows.json').open('w', encoding='utf-8') as output:
        output.write('{')
        for index, (slot, frame) in enumerate(inputs.frames.items()):
            if index: output.write(',')
            output.write(json.dumps(slot) + ':')
            frame.to_json(output, orient='records', date_format='iso', force_ascii=False)
        output.write('}')
    staging = folder / 'paper_staging'
    paper_writer(result, staging, entity='사용자 제출 자료', period='입력 조건 참조', prepared_by='검토자 미지정')
    for file in staging.iterdir():
        file.rename(paper_dir / file.name)
    staging.rmdir()
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
