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

    @classmethod
    def from_env(cls):
        if str(ROOT / 'src') not in sys.path:
            sys.path.insert(0, str(ROOT / 'src'))
        from audit_data_lab.kyc_settings import load_project_env
        load_project_env(ROOT)
        return cls(StorageConfig(Path(os.environ.get('AUDIT_RUNTIME_ROOT', ROOT / '.runtime')), job_ttl_seconds=int(os.environ.get('AUDIT_JOB_TTL_SECONDS', '3600'))), allow_ai=os.environ.get('AUDIT_ALLOW_AI', 'false').lower() == 'true', excel_node=os.environ.get('AUDIT_XLSX_NODE'), excel_modules=os.environ.get('AUDIT_XLSX_MODULES'))
