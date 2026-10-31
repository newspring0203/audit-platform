"""공통 응답 형식과 제한된 JSON 읽기."""
import asyncio
import json
from .storage import ServiceError

NO_STORE = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}

def public_job(row):
    return {'job_id': row['id'], 'module': row['module'], 'status': row['status'], 'parameters': json.loads(row['params']), 'created_at': row['created'], 'expires_at': row['expires'], 'uploaded_slots': list(json.loads(row['inputs'])), 'artifact': {'artifact_id': row['artifact'], 'size': row['artifact_size'], 'sha256': row['artifact_sha']} if row['artifact'] else None}

async def read_small_json(request, timeout_seconds):
    raw = bytearray()
    try:
        async with asyncio.timeout(timeout_seconds):
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 16384:
                    raise ServiceError('REQUEST_TOO_LARGE', '요청 조건이 너무 큽니다.', 413)
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ServiceError('INVALID_JSON', 'JSON 형식을 확인하세요.', 422) from None
    except TimeoutError:
        raise ServiceError('REQUEST_TIMEOUT', '요청 시간이 초과됐습니다.', 408) from None
