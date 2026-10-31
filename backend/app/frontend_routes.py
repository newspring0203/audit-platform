"""프론트엔드 정적 파일과 CSP."""
from fastapi.responses import FileResponse

def register_frontend_routes(app, root):
    @app.get('/')
    async def workspace():
        return FileResponse(root / 'frontend' / 'index.html', headers={'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})

    @app.get('/core/session.mjs')
    async def session_module():
        return FileResponse(root / 'frontend' / 'core' / 'session.mjs', media_type='text/javascript')

    @app.get('/workspace.js')
    async def workspace_js():
        return FileResponse(root / 'frontend' / 'workspace.js', media_type='text/javascript')

    @app.get('/chevron.svg')
    async def chevron():
        return FileResponse(root / 'frontend' / 'chevron.svg', media_type='image/svg+xml')

    @app.get('/workspace.css')
    async def workspace_css():
        return FileResponse(root / 'frontend' / 'workspace.css', media_type='text/css')
