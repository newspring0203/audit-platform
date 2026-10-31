"""서버 실행 설정."""
from dataclasses import dataclass
from pathlib import Path
import os
import sys
from .storage import StorageConfig

ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class AppConfig:
    storage: StorageConfig
    cleanup_interval_seconds: float = 30
    upload_timeout_seconds: float = 60
    max_run_seconds: int = 120
    max_workers: int = 2
    requests_per_minute: int = 120
    allow_ai: bool = False
    excel_node: str | None = None
    excel_modules: str | None = None

    mode: str = 'local'
    public_origin: str = ''
    max_demo_sessions: int = 100

    @classmethod
    def from_env(cls):
        if str(ROOT / 'src') not in sys.path:
            sys.path.insert(0, str(ROOT / 'src'))
        mode = os.environ.get('AUDIT_MODE', 'local')
        if mode not in {'local', 'demo', 'private'}:
            raise ValueError('AUDIT_MODE must be local, demo, or private')
        if mode == 'local':
            from audit_data_lab.kyc_settings import load_project_env
            load_project_env(ROOT)
        origin = os.environ.get('AUDIT_PUBLIC_ORIGIN', os.environ.get('RENDER_EXTERNAL_URL', '')).rstrip('/')
        if mode != 'local' and not origin.startswith('https://'):
            raise ValueError('Deployment requires an HTTPS AUDIT_PUBLIC_ORIGIN')
        def integer(name, default, maximum):
            value = int(os.environ.get(name, str(default)))
            if not 1 <= value <= maximum:
                raise ValueError(name + ' is outside its allowed range')
            return value
        storage = StorageConfig(
            Path(os.environ.get('AUDIT_RUNTIME_ROOT', str(ROOT / '.runtime') if mode == 'local' else '/tmp/audit-platform')),
            job_ttl_seconds=integer('AUDIT_JOB_TTL_SECONDS', 3600, 86400),
            token_ttl_seconds=3600,
            max_upload_bytes=integer('AUDIT_MAX_UPLOAD_BYTES', 20*1024*1024, 100*1024*1024),
            max_job_input_bytes=integer('AUDIT_MAX_JOB_INPUT_BYTES', 80*1024*1024, 200*1024*1024),
            max_jobs_total=integer('AUDIT_MAX_JOBS_TOTAL', 20, 100),
        )
        return cls(storage,
            cleanup_interval_seconds=integer('AUDIT_CLEANUP_SECONDS', 30, 3600),
            max_run_seconds=integer('AUDIT_RUN_TIMEOUT_SECONDS', 120, 600),
            max_workers=integer('AUDIT_ANALYSIS_WORKERS', 1, 4),
            requests_per_minute=integer('AUDIT_REQUESTS_PER_MINUTE', 120, 10000),
            allow_ai=os.environ.get('AUDIT_ALLOW_AI', 'false').lower() == 'true',
            excel_node=os.environ.get('AUDIT_XLSX_NODE'), excel_modules=os.environ.get('AUDIT_XLSX_MODULES'),
            mode=mode, public_origin=origin,
            max_demo_sessions=integer('AUDIT_MAX_DEMO_SESSIONS', 100, 1000))
