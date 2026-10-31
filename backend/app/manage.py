"""로컬 운영자 전용 개발 토큰 발급 도구. 공개 회원가입·SSO를 대신하지 않는다."""
import argparse,os
from pathlib import Path
from .storage import PrivateStore,StorageConfig


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    issue=sub.add_parser('issue-token');issue.add_argument('--tenant',required=True);issue.add_argument('--user',required=True);issue.add_argument('--token-file',required=True)
    issue.add_argument('--hours',type=float,default=1)
    sub.add_parser('cleanup')
    args=parser.parse_args()
    store=PrivateStore(StorageConfig(Path(args.root)))
    if args.command=='issue-token':
        if not 0<args.hours<=8:parser.error('토큰 유효기간은 0 초과 8시간 이하입니다.')
        target=Path(args.token_file)
        # 토큰은 한 번만 파일로 전달하고 stdout·셸 인자·소스코드에 출력하지 않는다.
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            token=store.issue_token(args.tenant,args.user,ttl=int(args.hours*3600))
            with os.fdopen(fd,'w') as f:f.write(token)
        except Exception:
            try:os.close(fd)
            except OSError:pass
            target.unlink(missing_ok=True);raise
        print('개발용 접근 토큰 파일을 생성했습니다. 키 값을 채팅이나 로그에 보내지 마세요.')
    else:
        from .jobs import JobManager
        store.acquire_server_lock()
        manager=JobManager(store)
        try:manager.cleanup();print('만료 작업 정리를 실행했습니다.')
        finally:manager.shutdown();store.release_server_lock()

if __name__=='__main__':main()
