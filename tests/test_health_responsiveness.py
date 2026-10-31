"""Storage contention must not block health checks on the event loop."""
import asyncio
import threading
import time
import unittest
from types import SimpleNamespace
import httpx
from fastapi import FastAPI
from backend.app.security import install_security

class HealthResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_responds_while_authentication_waits(self):
        release = threading.Event()
        started = threading.Event()
        class Store:
            def authenticate(self, token):
                started.set()
                release.wait(2)
                return SimpleNamespace(tenant_id='test', user_id='test')
        app = FastAPI()
        install_security(app, Store(), SimpleNamespace(mode='local', requests_per_minute=100), time.time)
        @app.get('/health')
        async def health(): return {'status':'ok'}
        @app.get('/api/probe')
        async def probe(): return {'ok':True}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            before = time.monotonic()
            pending = asyncio.create_task(client.get('/api/probe', headers={'Authorization':'Bearer test'}))
            try:
                while not started.is_set(): await asyncio.sleep(.01)
                response = await asyncio.wait_for(client.get('/health'), .5)
                self.assertEqual(response.status_code, 200)
                self.assertLess(time.monotonic()-before, 1)
            finally:
                release.set()
                await pending
