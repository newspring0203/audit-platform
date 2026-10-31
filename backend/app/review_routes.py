"""자료 버전·원본 조회·검토 기록 API."""
from datetime import datetime, timezone
import hashlib
import json
import uuid
import pandas as pd
from fastapi import Request
from fastapi.responses import JSONResponse
from .review_models import MaterialContext, Reference, ReviewNote
from .review_support import ReviewFiles
from .storage import ServiceError


def register_review_routes(app, store, small_json):
    files = ReviewFiles(store, small_json)
    @app.get('/api/jobs/{job_id}/materials')
    async def materials(job_id: str, request: Request):
        row, _ = files.owned(job_id, request)
        return {'datasets': files.clean_assets(json.loads(row['inputs'])), 'retention': '이 작업의 만료·삭제 시 자료 버전·검토 기록도 삭제됩니다.'}

    @app.patch('/api/jobs/{job_id}/materials/{slot}')
    async def material_context(job_id: str, slot: str, request: Request):
        value = await files.body(request, MaterialContext)
        with store.lock:
            row, _ = files.owned(job_id, request)
            if row['status'] != 'created':
                raise ServiceError('CONTEXT_FROZEN', '실행을 시작한 자료 정보는 변경할 수 없습니다.', 409)
            inputs = json.loads(row['inputs'])
            if slot not in inputs:
                raise ServiceError('INPUT_NOT_FOUND', '자료를 먼저 업로드하세요.', 404)
            inputs[slot]['context'] = value.model_dump()
            with store.connection() as db:
                db.execute('UPDATE jobs SET inputs=? WHERE id=?', (json.dumps(inputs), job_id))
        return files.clean_assets(inputs)[slot]

    @app.get('/api/jobs/{job_id}/materials/{slot}/compare')
    async def compare_versions(job_id: str, slot: str, request: Request, prior_version: str, keys: str, offset: int=0, limit: int=25):
        if offset < 0 or not 1 <= limit <= 100 or len(keys) > 1000:
            raise ServiceError('INVALID_PAGE', '키 또는 페이지 범위를 확인하세요.', 422)
        from audit_data_lab.dataset_compare import compare_datasets
        from audit_data_lab.validation import DataValidationError
        row, folder = files.owned(job_id, request)
        if row['status'] in {'uploading', 'running', 'queued'}:
            raise ServiceError('JOB_BUSY', '업로드 또는 분석 완료 후 비교하세요.', 409)
        assets = json.loads(row['inputs'])
        current = assets.get(slot)
        if not current:
            raise ServiceError('INPUT_NOT_FOUND', '자료가 없습니다.', 404)
        prior = next((h for h in current.get('history', []) if h.get('version_id', h['sha256']) == prior_version), None)
        if prior is None:
            raise ServiceError('VERSION_NOT_FOUND', '이 작업의 이전 버전이 아닙니다.', 404)

        def read_asset(asset):
            path = folder / 'inputs' / asset['stored_name']
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != asset['sha256']:
                raise ServiceError('SOURCE_HASH_MISMATCH', '자료 해시가 다릅니다. 원본을 다시 확인하세요.', 409)
            if asset['suffix'] == '.xlsx':
                frame = pd.read_excel(path, dtype='string', nrows=100001)
            else:
                encoding = 'utf-8-sig'
                try:
                    raw.decode(encoding)
                except UnicodeDecodeError:
                    encoding = 'cp949'
                frame = pd.read_csv(path, dtype='string', encoding=encoding, nrows=100001)
            if len(frame) > 100000 or len(frame.columns) > 256:
                raise ServiceError('DATASET_LIMIT', '비교할 자료의 크기 한도를 초과했습니다.', 422)
            return frame
        try:
            result = compare_datasets(read_asset(prior), read_asset(current), [k.strip() for k in keys.split(',') if k.strip()])
        except DataValidationError as error:
            return JSONResponse({'error': {'code': 'COMPARISON_INPUT_ISSUE', 'message': '비교 키가 양쪽 자료에서 비어 있지 않고 유일한지 확인하세요.', 'issues': error.to_dict()['errors']}}, status_code=422)
        except (UnicodeDecodeError, pd.errors.ParserError):
            raise ServiceError('INPUT_PARSE_ISSUE', '파일 형식을 확인하세요.', 422) from None
        total = len(result['changes'])
        result['changes'] = result['changes'][offset:offset + limit]
        return result | {'total': total, 'prior_version': prior_version, 'current_version': current.get('version_id', current['sha256']), 'period_basis': '제출자가 입력한 자료 기간이며 추출 완전성·기간 일치를 자동 입증하지 않습니다.'}

    @app.get('/api/jobs/{job_id}/review')
    async def review(job_id: str, request: Request):
        _, folder = files.owned(job_id, request, True)
        data = files.snapshot(folder)
        return {k: v for k, v in data.items() if k not in {'tables', 'trace'}} | {'tables': {k: {'columns': v['columns'], 'row_count': v['row_count']} for k, v in data['tables'].items()}, 'review_log': files.load(folder / 'review_log.json', {'revision': 0, 'events': [], 'references': {}})}

    @app.get('/api/jobs/{job_id}/review/tables/{table}')
    async def table_rows(job_id: str, table: str, request: Request, offset: int=0, limit: int=50):
        if offset < 0 or not 1 <= limit <= 100:
            raise ServiceError('INVALID_PAGE', '페이지 범위를 확인하세요.', 422)
        _, folder = files.owned(job_id, request, True)
        data = files.snapshot(folder)['tables'].get(table)
        if data is None:
            raise ServiceError('TABLE_NOT_FOUND', '결과 표가 없습니다.', 404)
        return {'columns': data['columns'], 'row_count': data['row_count'], 'rows': data['rows'][offset:offset + limit]}

    @app.get('/api/jobs/{job_id}/review/trace/{review_id}')
    async def trace(job_id: str, review_id: str, request: Request):
        _, folder = files.owned(job_id, request, True)
        data = files.snapshot(folder)
        entry = data['trace'].get(review_id)
        if entry is None:
            raise ServiceError('RECORD_NOT_FOUND', '결과 행이 없습니다.', 404)
        return entry | {'datasets': data['datasets']}

    @app.get('/api/jobs/{job_id}/review/sources/{slot}')
    async def source_rows(job_id: str, slot: str, request: Request, offset: int=0, limit: int=25, review_id: str=''):
        if offset < 0 or not 1 <= limit <= 100:
            raise ServiceError('INVALID_PAGE', '페이지 범위를 확인하세요.', 422)
        _, folder = files.owned(job_id, request, True)
        data = files.snapshot(folder)
        if slot not in data['datasets']:
            raise ServiceError('INPUT_NOT_FOUND', '입력 자료가 없습니다.', 404)
        entry = data['trace'].get(review_id)
        if entry is None:
            raise ServiceError('RECORD_NOT_FOUND', '출처를 확인할 결과 행을 지정하세요.', 404)
        rows = sorted({n for ref in entry['sources'] if ref['slot'] == slot for n in ref['rows']})
        sources = files.load(folder / 'source_rows.json')
        return {'total': len(rows), 'rows': [{'source_row': n, 'values': sources[slot][n - data['datasets'][slot].get('first_data_row', 2)]} for n in rows[offset:offset + limit]], 'dataset': data['datasets'][slot]}

    @app.post('/api/jobs/{job_id}/review/references', status_code=201)
    async def add_reference(job_id: str, request: Request):
        value = await files.body(request, Reference)
        with store.lock:
            _, folder = files.owned(job_id, request, True)
            log = files.load(folder / 'review_log.json', {'revision': 0, 'events': [], 'references': {}})
            if len(log['references']) >= 100:
                raise ServiceError('REFERENCE_LIMIT', '작업별 참조 등록 한도입니다.', 422)
            key = uuid.uuid4().hex
            log['references'][key] = value.model_dump() | {'verification_status': 'user_supplied_unverified', 'registered_by': request.state.principal.user_id}
            log['revision'] += 1
            files.save(folder / 'review_log.json', log)
        return {'reference_id': key, 'revision': log['revision'], 'reference': log['references'][key]}

    @app.put('/api/jobs/{job_id}/review/notes/{review_id}')
    async def note(job_id: str, review_id: str, request: Request):
        value = await files.body(request, ReviewNote)
        with store.lock:
            _, folder = files.owned(job_id, request, True)
            data = files.snapshot(folder)
            if review_id not in data['trace']:
                raise ServiceError('RECORD_NOT_FOUND', '결과 행이 없습니다.', 404)
            log = files.load(folder / 'review_log.json', {'revision': 0, 'events': [], 'references': {}})
            if value.revision != log['revision']:
                raise ServiceError('REVIEW_CONFLICT', '다른 변경이 있습니다. 결과를 새로 조회한 뒤 저장하세요.', 409)
            if set(value.reference_ids) - set(log['references']):
                raise ServiceError('REFERENCE_NOT_FOUND', '등록되지 않은 기준 참조입니다.', 422)
            if len(log['events']) >= 1000:
                raise ServiceError('REVIEW_LIMIT', '검토 이력 한도입니다. 기록을 내려받고 새 작업을 사용하세요.', 422)
            event = value.model_dump(exclude={'revision'}) | {'review_id': review_id, 'revision': log['revision'] + 1, 'reviewer': request.state.principal.user_id, 'at': datetime.now(timezone.utc).isoformat()}
            log['events'].append(event)
            log['revision'] += 1
            files.save(folder / 'review_log.json', log)
        return event

    @app.get('/api/jobs/{job_id}/review/export')
    async def export(job_id: str, request: Request):
        _, folder = files.owned(job_id, request, True)
        data = files.snapshot(folder)
        return JSONResponse({'run_id': data['run_id'], 'analysis_artifact_sha256': store.owned(job_id, request.state.principal).get('artifact_sha'), 'datasets': data['datasets'], 'review_log': files.load(folder / 'review_log.json', {'revision': 0, 'events': [], 'references': {}}), 'policy': '추가 검토 이력은 분석 시점 ZIP과 별도의 최신 기록입니다. TTL 이후 서버에서 삭제됩니다.'}, headers={'Content-Disposition': 'attachment; filename="review_history.json"'})
