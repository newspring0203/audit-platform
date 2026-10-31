"""새 기능 등록 시 API와 분석 실행기가 어긋나지 않는지 확인한다."""
from pathlib import Path
import sys
import unittest
import subprocess
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from backend.app.contracts import MODULES
from backend.app.analysis_dispatch import HANDLERS


class BackendStructureTests(unittest.TestCase):
    def test_every_api_module_has_one_analysis_handler(self):
        self.assertEqual(set(MODULES), set(HANDLERS))
        self.assertTrue(all(callable(handler) for handler in HANDLERS.values()))


class FreshServerImportTests(unittest.TestCase):
    def test_server_import_without_preloaded_src_path(self):
        env={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME'}}
        code="import sys;sys.path.insert(0,"+repr(str(ROOT))+");from backend.app.main import create_app;from backend.app.contracts import MODULES;assert callable(create_app);assert 'ar_confirmation' in MODULES;assert 'bank_confirmation' in MODULES"
        result=subprocess.run([sys.executable,'-I','-c',code],cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
