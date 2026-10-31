"""Bearer 인증·요청 제한·오류 응답."""
from collections import defaultdict, deque
from fastapi.responses import JSONResponse
from .http_helpers import NO_STORE
from .storage import ServiceError

class RateLimiter:

    def __init__(self, limit, clock):
        self.limit = limit
        self.clock = clock
        self.windows = defaultdict(deque)

    def check(self, key):
        now = self.clock()
        if key not in self.windows and len(self.windows) >= 2000:
            for old in list(self.windows):
                if not self.windows[old] or self.windows[old][-1] <= now - 60:
                    self.windows.pop(old, None)
            if len(self.windows) >= 2000:
                raise ServiceError('RATE_LIMIT', '요청이 너무 많습니다. 잠시 후 다시 시도하세요.', 429)
        window = self.windows[key]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= self.limit:
            raise ServiceError('RATE_LIMIT', '요청이 너무 많습니다. 잠시 후 다시 시도하세요.', 429)
        window.append(now)
        if len(self.windows) > 2000:
            for old in list(self.windows):
                if not self.windows[old] or self.windows[old][-1] <= now - 60:
                    self.windows.pop(old, None)

def install_security(app, store, config, clock):
    limiter = RateLimiter(config.requests_per_minute, clock)
    unauthenticated_limiter = RateLimiter(60, clock)
    def error_response(code, message, status):
        return JSONResponse({'error': {'code': code, 'message': message}}, status_code=status, headers=NO_STORE)

    @app.exception_handler(ServiceError)
    async def service_error(request, error):
        return error_response(error.code, error.message, error.status)

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        return error_response('INTERNAL_ERROR', '요청을 처리하지 못했습니다. 작업 식별자로 담당자에게 확인하세요.', 500)

    @app.middleware('http')
    async def security(request, call_next):
        try:
            if request.url.path.startswith('/api/'):
                header = request.headers.get('Authorization', '')
                if not header.startswith('Bearer '):
                    raise ServiceError('UNAUTHENTICATED', '인증이 필요합니다.', 401)
                principal = store.authenticate(header[7:])
                limiter.check((principal.tenant_id, principal.user_id))
                request.state.principal = principal
            response = await call_next(request)
        except ServiceError as error:
            if error.status == 401:
                try:
                    unauthenticated_limiter.check(('unauthenticated', request.client.host if request.client else 'unknown'))
                except ServiceError as limited:
                    error = limited
            response = error_response(error.code, error.message, error.status)
        except Exception as error:
            try:
                store.event('request_failed', code=type(error).__name__)
            except Exception:
                pass
            response = error_response('INTERNAL_ERROR', '요청을 처리하지 못했습니다. 작업 식별자로 담당자에게 확인하세요.', 500)
        for key, value in NO_STORE.items():
            response.headers[key] = value
        return response
