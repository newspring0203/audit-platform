"""API 조립 진입점."""
import time
from typing import Callable
from fastapi import FastAPI
from .config import AppConfig
from .frontend_routes import register_frontend_routes
from .config import ROOT
from .http_helpers import read_small_json
from .job_routes import register_job_routes
from .jobs import JobManager
from .lifecycle import create_lifespan
from .review_routes import register_review_routes
from .demo import register_demo_routes
from .security import install_security
from .storage import PrivateStore

def create_app(config=None, *, clock: Callable = time.time):
    config = config or AppConfig.from_env()
    store = PrivateStore(config.storage, clock=clock)
    manager = JobManager(
        store,
        max_workers=config.max_workers,
        max_run_seconds=config.max_run_seconds,
        allow_ai=config.allow_ai,
        excel_node=config.excel_node,
        excel_modules=config.excel_modules,
    )
    app = FastAPI(
        title="Audit Platform Private API",
        lifespan=create_lifespan(store, manager, config),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store
    app.state.manager = manager
    install_security(app, store, config, clock)

    async def small_json(request):
        return await read_small_json(request, config.upload_timeout_seconds)

    register_demo_routes(app, store, config)
    register_job_routes(app, store, manager, config, clock, small_json)
    register_review_routes(app, store, small_json)
    register_frontend_routes(app, ROOT)
    return app
