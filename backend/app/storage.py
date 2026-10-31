"""단일 서버 프로세스용 비공개 작업 저장소. 인증된 소유자만 접근한다."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib,json,os,secrets,shutil,sqlite3,threading,time,uuid
from pathlib import Path

class ServiceError(Exception):
    def __init__(self,code,message,status=400):self.code=code;self.message=message;self.status=status

@dataclass(frozen=True)
class Principal:
    tenant_id:str
    user_id:str
    token_digest:str
    expires_at:float

@dataclass(frozen=True)
class StorageConfig:
    root:Path
    job_ttl_seconds:int=3600
    token_ttl_seconds:int=3600
    max_upload_bytes:int=20*1024*1024
    max_job_input_bytes:int=80*1024*1024
    max_jobs_per_owner:int=3
    max_jobs_total:int=50
    event_ttl_seconds:int=86400


def identifier(value):
    try:
        if uuid.UUID(value).hex!=value:raise ValueError
    except (ValueError,TypeError,AttributeError):raise ServiceError('NOT_AVAILABLE','요청한 작업을 사용할 수 없습니다.',404)
    return value

class PrivateStore:
    def __init__(self,config,*,clock=time.time):
        if config.job_ttl_seconds<=0 or config.max_upload_bytes<=0:raise ValueError('저장 정책 설정 오류')
        self.config=config;self.clock=clock;self.lock=threading.RLock()
        self.root=Path(config.root).resolve()
        if self.root==Path('/') or self.root==Path.home():raise ValueError('전용 임시 폴더를 지정하세요.')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(self.root,0o700)
        self.jobs_root=self.root/'jobs';self.jobs_root.mkdir(exist_ok=True,mode=0o700)
        self.db=self.root/'metadata.sqlite3';self._server_lock=None
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS tokens(digest TEXT PRIMARY KEY, tenant TEXT NOT NULL, user TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,tenant TEXT NOT NULL,user TEXT NOT NULL,module TEXT NOT NULL,
                params TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,status TEXT NOT NULL,
                inputs TEXT NOT NULL DEFAULT '{}',artifact TEXT,artifact_size INTEGER,artifact_sha TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,event TEXT NOT NULL,at REAL NOT NULL,
                job TEXT,actor_hash TEXT,code TEXT);
            ''')
        os.chmod(self.db,0o600)

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.db,timeout=15);db.row_factory=sqlite3.Row
        db.execute('PRAGMA secure_delete=ON')
        try:
            with db:yield db
        finally:db.close()

    def acquire_server_lock(self):
        import fcntl
        file=open(self.root/'server.lock','a+')
        try:fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            file.close();raise RuntimeError('같은 저장소에 여러 서버 worker를 실행할 수 없습니다.') from None
        self._server_lock=file

    def release_server_lock(self):
        if self._server_lock:self._server_lock.close();self._server_lock=None

    def issue_token(self,tenant,user,*,ttl=None):
        if not tenant or not user or len(tenant)>100 or len(user)>100:raise ValueError('회사·사용자 식별자 확인 필요')
        token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
        expires=self.clock()+min(ttl or self.config.token_ttl_seconds,28800)
        with self.lock,self.connection() as db:db.execute('INSERT INTO tokens VALUES(?,?,?,?)',(digest,tenant,user,expires))
        return token

    def authenticate(self,token):
        if not isinstance(token,str) or len(token)<32 or len(token)>200:raise ServiceError('UNAUTHENTICATED','인증이 필요합니다.',401)
        digest=hashlib.sha256(token.encode()).hexdigest()
        with self.lock,self.connection() as db:row=db.execute('SELECT * FROM tokens WHERE digest=? AND expires>?',(digest,self.clock())).fetchone()
        if row is None:raise ServiceError('UNAUTHENTICATED','인증이 필요합니다.',401)
        return Principal(row['tenant'],row['user'],digest,row['expires'])

    def token_active(self,principal):
        with self.lock,self.connection() as db:
            return db.execute('SELECT 1 FROM tokens WHERE digest=? AND expires>?',(principal.token_digest,self.clock())).fetchone() is not None

    def revoke(self,principal):
        with self.lock,self.connection() as db:db.execute('DELETE FROM tokens WHERE digest=?',(principal.token_digest,))

    def event(self,event,job=None,principal=None,code=None):
        actor=hashlib.sha256((principal.tenant_id+'\0'+principal.user_id).encode()).hexdigest() if principal else None
        # 원본 파일명·경로·내용·금액·API 키·HTTP 본문을 기록하지 않는다.
        with self.connection() as db:db.execute('INSERT INTO events(event,at,job,actor_hash,code) VALUES(?,?,?,?,?)',(event,self.clock(),job,actor,code))

    def job_path(self,row):
        tenant=hashlib.sha256(row['tenant'].encode()).hexdigest()[:24]
        user=hashlib.sha256(row['user'].encode()).hexdigest()[:24]
        return self.jobs_root/tenant/user/identifier(row['id'])

    def _row(self,job_id):
        identifier(job_id)
        with self.connection() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row is None:raise ServiceError('NOT_AVAILABLE','요청한 작업을 사용할 수 없습니다.',404)
        return dict(row)

    def owned(self,job_id,principal):
        with self.lock:
            row=self._row(job_id)
            if row['tenant']!=principal.tenant_id or row['user']!=principal.user_id or row['expires']<=self.clock():
                raise ServiceError('NOT_AVAILABLE','요청한 작업을 사용할 수 없습니다.',404)
            return row

    def create_job(self,principal,module,parameters):
        with self.lock,self.connection() as db:
            now=self.clock()
            count=db.execute('SELECT count(*) FROM jobs WHERE tenant=? AND user=? AND expires>?',(principal.tenant_id,principal.user_id,now)).fetchone()[0]
            total=db.execute('SELECT count(*) FROM jobs WHERE expires>?',(now,)).fetchone()[0]
            if count>=self.config.max_jobs_per_owner or total>=self.config.max_jobs_total:
                raise ServiceError('JOB_LIMIT','작업 한도에 도달했습니다. 기존 작업을 삭제하거나 만료 후 다시 시도하세요.',429)
            job_id=uuid.uuid4().hex;row={'id':job_id,'tenant':principal.tenant_id,'user':principal.user_id}
            folder=self.job_path(row);folder.mkdir(parents=True,mode=0o700)
            for parent in [folder.parent,folder.parent.parent]:os.chmod(parent,0o700)
            expiry=now+self.config.job_ttl_seconds
            self.write_private(folder/'expiry.json',json.dumps({'expires':expiry}).encode())
            (folder/'inputs').mkdir(mode=0o700)
            db.execute('INSERT INTO jobs(id,tenant,user,module,params,created,expires,status) VALUES(?,?,?,?,?,?,?,?)',
                (job_id,principal.tenant_id,principal.user_id,module,json.dumps(parameters),now,expiry,'created'))
        self.event('job_created',job_id,principal)
        return self.owned(job_id,principal)

    @staticmethod
    def write_private(path,data):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(fd,'wb') as f:f.write(data)

    def begin_upload(self,job_id,principal,slot,suffix):
        with self.lock:
            row=self.owned(job_id,principal)
            if row['status']!='created':raise ServiceError('JOB_BUSY','현재 작업에는 파일을 추가할 수 없습니다.',409)
            inputs=json.loads(row['inputs'])
            if sum(1+len(item.get('history',[])) for item in inputs.values())>=30:raise ServiceError('VERSION_LIMIT','작업의 자료 버전 한도에 도달했습니다.',422)
            used=sum(item['size']+sum(h['size'] for h in item.get('history',[])) for item in inputs.values())
            path=self.job_path(row)/'inputs'/('upload_'+uuid.uuid4().hex+'.part')
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            with self.connection() as db:db.execute("UPDATE jobs SET status='uploading' WHERE id=?",(job_id,))
            return path,os.fdopen(fd,'wb'),used,row['expires']

    def commit_upload(self,job_id,principal,slot,suffix,part,size,digest,display_name=None):
        with self.lock:
            row=self.owned(job_id,principal)
            if row['status']!='uploading':raise ServiceError('JOB_BUSY','업로드를 완료할 수 없습니다.',409)
            inputs=json.loads(row['inputs']);folder=self.job_path(row)/'inputs'
            final=folder/(uuid.uuid4().hex+suffix)
            os.replace(part,final)
            old=inputs.get(slot)
            history=old.get('history',[])+[{k:v for k,v in old.items() if k!='history'}] if old else []
            inputs[slot]={'stored_name':final.name,'size':size,'sha256':digest,'suffix':suffix,'version_id':uuid.uuid4().hex,'uploaded_at':self.clock(),'display_name':display_name or slot+suffix,'history':history,'context':{}}
            with self.connection() as db:db.execute("UPDATE jobs SET status='created',inputs=? WHERE id=?",(json.dumps(inputs),job_id))
            # 이전 버전은 작업 TTL 내에서만 보관하며 업로드 용량에 합산한다.
        self.event('input_uploaded',job_id,principal)

    def abort_upload(self,job_id,part):
        with self.lock:
            part.unlink(missing_ok=True)
            with self.connection() as db:db.execute("UPDATE jobs SET status='created' WHERE id=? AND status='uploading'",(job_id,))

    def update_status(self,job_id,status):
        with self.lock,self.connection() as db:db.execute('UPDATE jobs SET status=? WHERE id=?',(status,job_id))

    def finalize(self,job_id):
        with self.lock:
            row=self._row(job_id)
            if row['expires']<=self.clock():return False
            bundle=self.job_path(row)/'bundle.zip'
            if not bundle.is_file() or bundle.is_symlink():raise ServiceError('REPORT_UNAVAILABLE','결과 파일을 확인할 수 없습니다.',500)
            aid=uuid.uuid4().hex
            with bundle.open('rb') as source: digest=hashlib.file_digest(source, 'sha256').hexdigest()
            with self.connection() as db:db.execute("UPDATE jobs SET status='completed',artifact=?,artifact_size=?,artifact_sha=? WHERE id=?",(aid,bundle.stat().st_size,digest,job_id))
            self.event('job_completed',job_id)
            return True

    def open_download(self,job_id,artifact_id,principal):
        with self.lock:
            row=self.owned(job_id,principal)
            if row['status']!='completed' or row['artifact']!=artifact_id:
                raise ServiceError('NOT_AVAILABLE','요청한 결과를 사용할 수 없습니다.',404)
            file=self.job_path(row)/'bundle.zip'
            try:fd=os.open(file,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
            except OSError:raise ServiceError('NOT_AVAILABLE','요청한 결과를 사용할 수 없습니다.',404) from None
            self.event('download_opened',job_id,principal)
            return os.fdopen(fd,'rb'),row

    def delete(self,job_id,*,principal=None):
        with self.lock:
            try:row=self.owned(job_id,principal) if principal else self._row(job_id)
            except ServiceError:
                if principal:raise
                return
            path=self.job_path(row)
            # 삭제 실패 시 메타데이터를 유지하여 다음 정리에서 재시도한다.
            if path.exists():shutil.rmtree(path)
            with self.connection() as db:db.execute('DELETE FROM jobs WHERE id=?',(job_id,))
            self.event('job_deleted',job_id,principal)

    def expired_ids(self):
        with self.lock,self.connection() as db:return [r[0] for r in db.execute('SELECT id FROM jobs WHERE expires<=?',(self.clock(),))]

    def prune_and_orphans(self):
        with self.lock,self.connection() as db:
            now=self.clock();db.execute('DELETE FROM tokens WHERE expires<=?',(now,));db.execute('DELETE FROM events WHERE at<?',(now-self.config.event_ttl_seconds,))
            live={r[0] for r in db.execute('SELECT id FROM jobs')}
            for directory in self.jobs_root.glob('*/*/*'):
                if directory.name in live:continue
                if directory.is_symlink():directory.unlink();continue
                try:expires=float(json.loads((directory/'expiry.json').read_text())['expires'])
                except (OSError,ValueError,KeyError,TypeError):expires=directory.stat().st_mtime+self.config.job_ttl_seconds
                if expires<=now and directory.is_dir():shutil.rmtree(directory)
