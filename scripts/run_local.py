"""로컬 MVP 실행기. 토큰은 화면·셸 인자에 출력하지 않는다."""
from pathlib import Path
import os,sys,socket
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    from backend.app.storage import PrivateStore,StorageConfig,ServiceError
    try:port=int(os.environ.get('AUDIT_PORT','8000'))
    except ValueError:raise SystemExit('AUDIT_PORT는 숫자여야 합니다.')
    if not 1024<=port<=65535:raise SystemExit('AUDIT_PORT는 1024~65535 범위여야 합니다.')
    root=Path(os.environ.get('AUDIT_RUNTIME_ROOT',ROOT/'.runtime')).resolve()
    store=PrivateStore(StorageConfig(root));token_path=root/'reviewer.token';active=False
    if token_path.exists():
        if token_path.is_symlink():raise SystemExit('토큰 파일이 심볼릭 링크입니다. 전용 저장소를 확인하세요.')
        try:store.authenticate(token_path.read_text().strip());active=True
        except ServiceError:pass
    if not active:store.write_private(token_path,store.issue_token('local-development','local-reviewer').encode())
    os.environ['AUDIT_RUNTIME_ROOT']=str(root)
    os.chdir(ROOT)
    print('Audit Platform 로컬 MVP',flush=True)
    print(f'접속: http://127.0.0.1:{port}',flush=True)
    print(f'로컬 편집기로 토큰 파일을 열어 웹 연결 칸에 입력하세요: {token_path}',flush=True)
    print('개발용 로컬 인증입니다. 종료: Ctrl+C. 기본 작업 보관: 1시간.',flush=True)
    os.execv(sys.executable,[sys.executable,'-m','uvicorn','backend.app.main:create_app','--factory','--host','127.0.0.1','--port',str(port),'--workers','1','--no-access-log'])

if __name__=='__main__':main()
