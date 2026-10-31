"""서버 시작·주기 정리·종료."""
import asyncio
from contextlib import asynccontextmanager

def create_lifespan(store, manager, config):
    @asynccontextmanager
    async def lifespan(app):
        store.acquire_server_lock()
        manager.cleanup()
        manager.recover()

        async def periodic():
            while True:
                await asyncio.sleep(config.cleanup_interval_seconds)
                try:
                    await asyncio.to_thread(manager.cleanup)
                except Exception:
                    store.event('cleanup_failed', code='CLEANUP_FAILED')
        task = asyncio.create_task(periodic())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await asyncio.to_thread(manager.shutdown)
            store.release_server_lock()
    return lifespan
