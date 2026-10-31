"""Anonymous, isolated portfolio sessions using server-owned synthetic fixtures only."""
import json, secrets
from pathlib import Path
from fastapi import Request
from fastapi.responses import JSONResponse
from .config import ROOT
from .http_helpers import NO_STORE
from .storage import ServiceError

COOKIE = '__Host-audit_demo'
FIXTURES = json.loads((Path(__file__).with_name('demo_fixtures.json')).read_text())

def register_demo_routes(app, store, config):
    @app.get('/deployment-info')
    async def deployment_info():
        return {'mode': config.mode, 'demo_modules': list(FIXTURES) if config.mode == 'demo' else [],
                'demo_parameters': {name: fixture['parameters'] for name, fixture in FIXTURES.items()} if config.mode == 'demo' else {},
                'session_seconds': 3600, 'job_ttl_seconds': config.storage.job_ttl_seconds}

    @app.post('/demo/session')
    async def demo_session(request: Request):
        if config.mode != 'demo':
            raise ServiceError('NOT_AVAILABLE', '데모 모드가 아닙니다.', 404)
        # Middleware validates origin, custom header and rate limit before issuance.
        existing = request.cookies.get(COOKIE)
        if existing:
            try:
                store.authenticate(existing)
                return JSONResponse({'status':'connected'}, headers=NO_STORE)
            except ServiceError:
                pass
        with store.lock, store.connection() as db:
            count = db.execute('SELECT count(*) FROM tokens WHERE expires>?', (store.clock(),)).fetchone()[0]
            if count >= config.max_demo_sessions:
                raise ServiceError('SESSION_LIMIT', '데모 이용자가 많습니다. 잠시 후 다시 접속하세요.', 429)
            token = store.issue_token('portfolio-demo', secrets.token_hex(16), ttl=3600)
        response = JSONResponse({'status':'connected'}, headers=NO_STORE)
        response.set_cookie(COOKIE, token, max_age=3600, httponly=True, secure=True, samesite='strict', path='/')
        return response
