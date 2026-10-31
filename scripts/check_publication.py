"""Inspect every Git-tracked/staged file without printing secret values."""
from pathlib import Path
import re, subprocess, sys, zipfile
ROOT = Path(__file__).resolve().parents[1]
BLOCKED = {'.env', '.runtime', '.venv', 'node_modules', 'notebooks', '__pycache__'}
PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'(?<![\w-])(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})'),
    re.compile(rb'(?i)(?:DART_API_KEY|OPENAI_API_KEY|ACCESS_TOKEN|AUTH_TOKEN)\s*[=:]\s*["\']?[A-Za-z0-9_-]{20,}'),
]
def main():
    names = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    issues=[]
    for name in filter(None,names):
        path=Path(name); full=ROOT/path
        if not full.is_file():
            issues.append((name,'missing tracked file')); continue
        if full.is_symlink():
            issues.append((name,'symlink')); continue
        if (set(path.parts)&BLOCKED or name.startswith(('data/raw/','data/processed/','data/evidence/','outputs/','submission/evidence/')) or path.suffix in {'.token','.sqlite','.sqlite3','.db','.log'} or (path.name.startswith('.env.') and path.name!='.env.example')):
            issues.append((name,'private path')); continue
        data=full.read_bytes()
        if any(pattern.search(data) for pattern in PATTERNS): issues.append((name,'possible secret'))
        if path.suffix=='.xlsx':
            if not name.startswith(('data/demo/','submission/demo_inputs/')):
                issues.append((name,'unapproved spreadsheet'))
            else:
                with zipfile.ZipFile(full) as archive:
                    if any(any(pattern.search(archive.read(item)) for pattern in PATTERNS) for item in archive.namelist()): issues.append((name,'possible secret in XLSX'))
    for name,reason in issues: print(f'BLOCKED: {name}: {reason}')
    print(f'Publication check: {len(list(filter(None,names)))} files, {len(issues)} findings. No secret values printed.')
    return bool(issues)
if __name__=='__main__': sys.exit(main())
