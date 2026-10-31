"""작업 실행·시간 제한·삭제 조정. 단일 ASGI 프로세스만 지원한다."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,os,signal,subprocess,sys,threading,zipfile
from .storage import ServiceError

class JobManager:
    def __init__(self,store,*,max_workers=2,max_run_seconds=120,allow_ai=False,excel_node=None,excel_modules=None):
        self.store=store;self.max_run_seconds=max_run_seconds;self.allow_ai=allow_ai
        self.excel_node=excel_node;self.excel_modules=excel_modules
        self.pool=ThreadPoolExecutor(max_workers=max_workers,thread_name_prefix='audit-job')
        self.lock=threading.RLock();self.processes={};self.futures={};self.closing=False

    def start(self,job_id,principal,*,dart_api_key=None):
        with self.lock:
            row=self.store.owned(job_id,principal)
            if row['status']!='created':raise ServiceError('JOB_BUSY','이미 처리 중이거나 완료된 작업입니다.',409)
            self.store.update_status(job_id,'queued')
            self.futures[job_id]=self.pool.submit(self._execute,job_id,dart_api_key=dart_api_key)
        return self.store.owned(job_id,principal)

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=10)

    def _issue_bundle(self,row,code,message):
        folder=self.store.job_path(row)
        # 이미 삭제된 작업 디렉터리를 다시 생성하지 않는다.
        if not folder.is_dir():return
        payload={'execution_status':'not_executed_system_issue','code':code,'message':message,
                 'suggested_review':'작업 식별자로 담당자에게 확인을 요청하세요. 원본·키를 보내지 마세요.'}
        with zipfile.ZipFile(folder/'bundle.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('review/processing_issue.json',json.dumps(payload,ensure_ascii=False,indent=2))
        os.chmod(folder/'bundle.zip',0o600)

    def _execute(self,job_id,*,dart_api_key=None):
        process=None
        try:
            with self.lock:
                if self.closing:return
                row=self.store._row(job_id)
                if row['status']!='queued' or row['expires']<=self.store.clock():return
                self.store.update_status(job_id,'running');folder=self.store.job_path(row)
                spec={'job_id':job_id,'directory':str(folder),'module':row['module'],
                    'parameters':json.loads(row['params']),'inputs':json.loads(row['inputs']),
                    'allow_ai':self.allow_ai,'excel_node':self.excel_node,'excel_modules':self.excel_modules}
                self.store.write_private(folder/'spec.json',json.dumps(spec).encode())
                # 자식 프로세스가 만드는 파일도 소유자만 접근하게 제한한다.
                temp=folder/'tmp';temp.mkdir(mode=0o700,exist_ok=True)
                allowed={'PATH','HOME','LANG','LC_ALL','TZ','SSL_CERT_FILE','SSL_CERT_DIR','NODE_EXTRA_CA_CERTS'}
                env={k:v for k,v in os.environ.items() if k in allowed}
                if row['module']=='kyc':
                    for key in ['DART_API_KEY','OPENAI_MODEL']:
                        if key in os.environ and (key != 'DART_API_KEY' or dart_api_key is None):env[key]=os.environ[key]
                    if self.allow_ai and json.loads(row['params']).get('with_ai') and 'OPENAI_API_KEY' in os.environ:
                        env['OPENAI_API_KEY']=os.environ['OPENAI_API_KEY']
                env.update({'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1','TMPDIR':str(temp),'TMP':str(temp),'TEMP':str(temp)})
                process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('worker.py')),str(folder/'spec.json')],
                    stdin=subprocess.PIPE if dart_api_key else subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    start_new_session=True,env=env,umask=0o077)
                # Visitor credentials never enter spec.json, SQLite, argv, or child environment.
                # A private anonymous pipe delivers the key to this job's worker only.
                if dart_api_key:
                    try:
                        process.stdin.write(dart_api_key.encode('ascii'))
                        process.stdin.close()
                    finally:
                        dart_api_key = None
                self.processes[job_id]=process
                deadline=min(self.max_run_seconds,max(0.1,row['expires']-self.store.clock()))
            timed_out=False
            try:process.wait(timeout=deadline)
            except subprocess.TimeoutExpired:
                self.stop_process(process);timed_out=True
            with self.lock:
                try:row=self.store._row(job_id)
                except ServiceError:return
                if row['expires']<=self.store.clock():self.store.delete(job_id);return
                if timed_out:self._issue_bundle(row,'PROCESSING_TIMEOUT','처리 시간 한도를 초과해 계산을 완료하지 못했습니다.')
                elif process.returncode!=0:self._issue_bundle(row,'PROCESSING_FAILED','내부 처리 문제로 계산을 완료하지 못했습니다.')
                self.store.finalize(job_id)
        except Exception:
            with self.lock:
                try:
                    row=self.store._row(job_id)
                    if row['expires']>self.store.clock():
                        self._issue_bundle(row,'PROCESSING_FAILED','처리 문제로 계산 결과를 생성하지 못했습니다.')
                        self.store.finalize(job_id)
                except Exception:pass
        finally:
            dart_api_key = None
            with self.lock:self.processes.pop(job_id,None);self.futures.pop(job_id,None)

    def delete(self,job_id,principal=None):
        with self.lock:
            if principal:self.store.owned(job_id,principal)
            future=self.futures.get(job_id)
            if future and future.cancel():self.futures.pop(job_id,None)
            process=self.processes.get(job_id)
            if process:self.stop_process(process)
            self.store.delete(job_id,principal=principal)

    def cleanup(self):
        for job_id in self.store.expired_ids():
            try:self.delete(job_id)
            except Exception:self.store.event('cleanup_failed',job_id,code='DELETE_FAILED')
        self.store.prune_and_orphans()

    def recover(self):
        # 이전 서버가 끝내지 못한 실행은 재사용하지 않고 원인을 담은 결과로 표시한다.
        with self.store.connection() as db:
            rows=[dict(r) for r in db.execute("SELECT * FROM jobs WHERE status IN ('queued','running','uploading')")]
        for row in rows:
            if row['expires']<=self.store.clock():self.delete(row['id']);continue
            if row['status']=='uploading':
                for part in (self.store.job_path(row)/'inputs').glob('*.part'):part.unlink(missing_ok=True)
                self.store.update_status(row['id'],'created')
            else:
                self._issue_bundle(row,'SERVER_RESTARTED','서버 재시작으로 이전 처리를 완료하지 못했습니다. 새 작업으로 재실행하세요.')
                self.store.finalize(row['id'])

    def shutdown(self):
        with self.lock:
            self.closing=True
            for process in list(self.processes.values()):self.stop_process(process)
        self.pool.shutdown(wait=True,cancel_futures=True)
