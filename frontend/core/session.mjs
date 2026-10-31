/** 인증·요청·세션 타이머. 토큰은 메모리에만 보관한다. */
export class SessionCancelled extends Error {
    constructor(){super('연결이 변경되어 이전 요청을 취소했습니다.');this.name='SessionCancelled';}
}
export class ApiError extends Error {
    constructor(message,status=0,code='REQUEST_FAILED'){super(message);this.name='ApiError';this.status=status;this.code=code;}
}
export class SessionClient {
    constructor({fetchImpl=globalThis.fetch.bind(globalThis),onSessionChange=()=>{}}={}){
        this.fetchImpl=fetchImpl;this.onSessionChange=onSessionChange;
        this._token='';this._epoch=0;this._attempt=0;this._probe=null;
        this._requests=new Set();this._timers=new Set();
    }
    get token(){return this._token;}
    get epoch(){return this._epoch;}
    isCurrent(epoch){return epoch===this._epoch;}
    assertCurrent(epoch){if(!this.isCurrent(epoch))throw new SessionCancelled();}
    _cancelWork(){
        for(const controller of this._requests)controller.abort();this._requests.clear();
        for(const timer of this._timers)clearTimeout(timer);this._timers.clear();
    }
    _change(token,reason){this._cancelWork();this._epoch++;this._token=token;this.onSessionChange(reason);}
    disconnect(reason='disconnected'){
        this._attempt++;this._probe?.abort();this._probe=null;this._change('',reason);
    }
    setTimer(callback,delay){
        const epoch=this.epoch;
        const timer=setTimeout(()=>{this._timers.delete(timer);if(this.isCurrent(epoch))callback();},delay);
        this._timers.add(timer);return timer;
    }
    clearTimer(timer){clearTimeout(timer);this._timers.delete(timer);}
    _headers(token,extra){const headers=new Headers(extra);if(token!=='cookie-session')headers.set('Authorization','Bearer '+token);headers.set('X-Audit-Request','1');return headers;}
    _path(path){if(typeof path!=='string'||/^(?:[a-z][a-z0-9+.-]*:|\/)/i.test(path))throw new ApiError('API 경로를 확인하세요.');return '/api/'+path;}
    async _error(response,check){
        let data;try{data=await response.json();}catch{}check();
        const code=data?.error?.code||'HTTP_'+response.status;
        const message=response.status===401?'인증을 확인하지 못했습니다. 토큰이 올바른지, 만료되었거나 로그아웃된 상태인지 확인하세요.':data?.error?.message||`요청 실패 (${response.status})`;
        return new ApiError(`${message} [${code}]`,response.status,code);
    }
    async connect(candidate){
        if(typeof candidate!=='string'||!candidate.trim())throw new ApiError('접근 토큰을 입력하세요.');
        candidate=candidate.trim();this._probe?.abort();const controller=new AbortController();this._probe=controller;
        const attempt=++this._attempt;const check=()=>{if(attempt!==this._attempt)throw new SessionCancelled();};
        try{
            const response=await this.fetchImpl(this._path('features'),{headers:this._headers(candidate),cache:'no-store',redirect:'error',signal:controller.signal});check();
            if(!response.ok)throw await this._error(response,check);
            const data=await response.json();check();
            if(!Array.isArray(data?.features))throw new ApiError('기능 목록 응답 형식을 확인하세요.');
            this._change(candidate,'connected');return data;
        }catch(error){check();if(error?.name==='AbortError')throw new SessionCancelled();throw error;}
        finally{if(this._probe===controller)this._probe=null;}
    }
    async connectDemo(){
        this.disconnect();
        const controller=new AbortController();this._probe=controller;
        const attempt=++this._attempt;const check=()=>{if(attempt!==this._attempt)throw new SessionCancelled();};
        try{
            const response=await this.fetchImpl('/demo/session',{method:'POST',headers:{'X-Audit-Request':'1'},credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal});check();
            if(!response.ok)throw await this._error(response,check);
            const features=await this.fetchImpl(this._path('features'),{credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal});check();
            if(!features.ok)throw await this._error(features,check);
            const data=await features.json();check();
            if(!Array.isArray(data?.features))throw new ApiError('기능 목록을 확인하지 못했습니다.');
            this._change('cookie-session','connected');return data;
        }catch(error){check();if(error?.name==='AbortError')throw new SessionCancelled();throw error;}
        finally{if(this._probe===controller)this._probe=null;}
    }
    async request(path,options={},mode='json'){
        if(!this.token)throw new ApiError('먼저 토큰으로 연결하세요.',401,'NOT_CONNECTED');
        const epoch=this.epoch,token=this.token,controller=new AbortController();this._requests.add(controller);
        const check=()=>this.assertCurrent(epoch);
        try{
            const response=await this.fetchImpl(this._path(path),{...options,headers:this._headers(token,options.headers),cache:'no-store',redirect:'error',signal:controller.signal});check();
            if(!response.ok){const error=await this._error(response,check);if(response.status===401){check();this.disconnect('unauthenticated');}error.sessionEpoch=this.epoch;throw error;}
            const data=response.status===204?null:mode==='blob'?await response.blob():await response.json();check();return data;
        }catch(error){if(!this.isCurrent(epoch)&&!(error instanceof ApiError&&error.status===401))throw new SessionCancelled();throw error;}
        finally{this._requests.delete(controller);}
    }
    async logout(){
        const token=this.token;this.disconnect('logout');const epoch=this.epoch;if(!token)return;
        const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),10000);
        try{
            const response=await this.fetchImpl(this._path('logout'),{method:'POST',headers:this._headers(token),cache:'no-store',redirect:'error',signal:controller.signal});this.assertCurrent(epoch);
            if(!response.ok&&response.status!==401)throw new ApiError('로컬 연결은 해제했지만 서버의 토큰 폐기는 확인하지 못했습니다.');
        }catch(error){this.assertCurrent(epoch);throw new ApiError('로컬 연결은 해제했지만 서버의 토큰 폐기는 확인하지 못했습니다.');}
        finally{clearTimeout(timeout);}
    }
}
