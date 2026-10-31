"""작업·업로드·다운로드 API."""
import asyncio
import csv
import hashlib
import io
import json
from .demo import FIXTURES
from .config import ROOT
from urllib.parse import unquote
from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError
from .contracts import NewJob, MODULES
from .http_helpers import NO_STORE, public_job
from .storage import ServiceError
from .ui_schema import module_ui, TEMPLATES
from .uploads import filename_suffix, validate_upload

def register_job_routes(app, store, manager, config, clock, small_json):
    @app.get('/health')
    async def health():
        return {'status': 'ok'}

    @app.get('/api/features')
    async def features():
        return {'features': [{'module': name, 'inputs': value['inputs'], 'required_inputs': value['required_inputs'], 'optional_inputs': value['optional_inputs'], 'parameters': sorted(value['parameters']), 'ui': module_ui()[name], 'input_columns': TEMPLATES.get(name, {})} for name, value in MODULES.items() if config.mode != 'demo' or name in FIXTURES], 'downloads': '기능별 검토 결과 ZIP; CSV·JSON·Markdown 포함, 서버 렌더러 설정 시 Excel 포함', 'cache_policy': {'customer_data': 'no-store', 'public_disclosures': 'not_enabled'}}

    @app.get('/api/jobs')
    async def list_jobs(request: Request):
        principal = request.state.principal
        with store.lock, store.connection() as db:
            rows = db.execute('SELECT * FROM jobs WHERE tenant=? AND user=? AND expires>? ORDER BY created DESC', (principal.tenant_id, principal.user_id, clock())).fetchall()
        return {'jobs': [public_job(dict(row)) for row in rows]}

    @app.get('/api/input-templates/{module}/{slot}')
    async def input_template(module: str, slot: str):
        fields = TEMPLATES.get(module, {}).get(slot)
        if not fields:
            raise ServiceError('TEMPLATE_NOT_AVAILABLE', '이 입력은 고정 컬럼 템플릿이 없습니다.', 404)
        text = io.StringIO()
        csv.writer(text).writerow(fields)
        return Response(('\ufeff' + text.getvalue()).encode(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="' + module + '_' + slot + '_template.csv"'})

    @app.post('/api/jobs', status_code=201)
    async def new_job(request: Request):
        payload = await small_json(request)
        try:
            spec = NewJob.model_validate(payload).checked()
        except ValidationError:
            raise ServiceError('INVALID_JOB_REQUEST', '기능·조건 형식을 확인하세요. 소유자나 API 키는 요청으로 지정할 수 없습니다.', 422) from None
        if config.mode == 'demo':
            if spec.module not in FIXTURES:
                raise ServiceError('DEMO_MODULE_DISABLED', '이 기능은 로컬 환경에서 사용할 수 있습니다.', 403)
            # Demo conditions are reproducible and cannot invoke external services.
            spec = NewJob(module=spec.module, parameters=FIXTURES[spec.module]['parameters'])
        await asyncio.to_thread(manager.cleanup)
        return public_job(store.create_job(request.state.principal, spec.module, spec.parameters))

    @app.get('/api/jobs/{job_id}')
    async def job_status(job_id: str, request: Request):
        return public_job(store.owned(job_id, request.state.principal))

    @app.put('/api/jobs/{job_id}/inputs/{slot}')
    async def upload(job_id: str, slot: str, request: Request):
        if config.mode == 'demo':
            raise ServiceError('DEMO_UPLOAD_DISABLED', '공개 데모는 합성 샘플 자료만 사용합니다.', 403)
        principal = request.state.principal
        row = store.owned(job_id, principal)
        if slot not in MODULES[row['module']]['inputs']:
            raise ServiceError('INVALID_INPUT_SLOT', '이 기능에서 받지 않는 입력입니다.', 422)
        suffix = filename_suffix(request.headers.get('X-Filename', ''))
        try:
            length = int(request.headers.get('Content-Length', '0'))
        except ValueError:
            raise ServiceError('INVALID_LENGTH', '업로드 크기를 확인하세요.', 422) from None
        if length > config.storage.max_upload_bytes:
            raise ServiceError('FILE_TOO_LARGE', '파일 크기 한도를 초과합니다.', 413)
        part, file, used, expires = store.begin_upload(job_id, principal, slot, suffix)
        size = 0
        digest = hashlib.sha256()
        try:
            async with asyncio.timeout(min(config.upload_timeout_seconds, max(0.1, expires - clock()))):
                async for chunk in request.stream():
                    if clock() >= expires:
                        raise ServiceError('NOT_AVAILABLE', '작업이 만료됐습니다.', 404)
                    size += len(chunk)
                    if size > config.storage.max_upload_bytes or size + used > config.storage.max_job_input_bytes:
                        raise ServiceError('FILE_TOO_LARGE', '업로드 또는 작업 전체 용량 한도를 초과합니다.', 413)
                    file.write(chunk)
                    digest.update(chunk)
            file.close()
            await asyncio.to_thread(validate_upload, part, suffix)
            store.commit_upload(job_id, principal, slot, suffix, part, size, digest.hexdigest(), display_name=unquote(request.headers.get('X-Filename', ''))[:160].replace('\x00', ''))
        except BaseException as error:
            file.close()
            store.abort_upload(job_id, part)
            if isinstance(error, TimeoutError):
                raise ServiceError('UPLOAD_TIMEOUT', '업로드 시간이 초과됐습니다.', 408) from None
            raise
        return {'slot': slot, 'size': size, 'status': 'uploaded'}

    @app.post('/api/jobs/{job_id}/run', status_code=202)
    async def start_job(job_id: str, request: Request):
        if config.mode == 'demo':
            row = store.owned(job_id, request.state.principal)
            if row['status'] == 'created' and not json.loads(row['inputs']):
                fixture = FIXTURES[row['module']]
                for slot, name in fixture['inputs'].items():
                    source = ROOT / 'data' / 'demo' / name
                    data = source.read_bytes()
                    part, file, _, _ = store.begin_upload(job_id, request.state.principal, slot, source.suffix)
                    try:
                        with file:
                            file.write(data)
                        store.commit_upload(job_id, request.state.principal, slot, source.suffix, part, len(data), hashlib.sha256(data).hexdigest(), display_name=source.name)
                    except BaseException:
                        file.close()
                        store.abort_upload(job_id, part)
                        raise
        return public_job(manager.start(job_id, request.state.principal))

    @app.get('/api/jobs/{job_id}/downloads/{artifact_id}')
    async def download(job_id: str, artifact_id: str, request: Request):
        principal = request.state.principal
        file, row = store.open_download(job_id, artifact_id, principal)

        async def content():
            try:
                while clock() < row['expires'] and clock() < principal.expires_at:
                    try:
                        store.owned(job_id, principal)
                        if not store.token_active(principal):
                            break
                    except ServiceError:
                        break
                    chunk = await asyncio.to_thread(file.read, 256 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                file.close()
        return StreamingResponse(content(), media_type='application/zip', headers={**NO_STORE, 'Content-Disposition': 'attachment; filename="audit_review.zip"', 'X-Artifact-SHA256': row['artifact_sha']})

    @app.delete('/api/jobs/{job_id}', status_code=204)
    async def delete_job(job_id: str, request: Request):
        await asyncio.to_thread(manager.delete, job_id, request.state.principal)
        return Response(status_code=204, headers=NO_STORE)

    @app.post('/api/logout', status_code=204)
    async def logout(request: Request):
        store.revoke(request.state.principal)
        return Response(status_code=204, headers=NO_STORE)
