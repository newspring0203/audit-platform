import test from 'node:test';
import assert from 'node:assert/strict';
import {SessionClient,SessionCancelled,ApiError} from '../frontend/core/session.mjs';
const ok=(data={features:[]})=>new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});
const unauthorized=()=>new Response(JSON.stringify({error:{code:'UNAUTHENTICATED',message:'인증이 필요합니다.'}}),{status:401});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const wait=ms=>new Promise(r=>setTimeout(r,ms));

test('valid connection commits once and keeps credentials in memory',async()=>{const events=[];const c=new SessionClient({fetchImpl:async()=>ok(),onSessionChange:r=>events.push(r)});await c.connect('valid');assert.equal(c.token,'valid');assert.equal(c.epoch,1);assert.deepEqual(events,['connected']);});
test('invalid reconnect preserves the working connection and does not claim expiry',async()=>{let bad=false;const events=[];const c=new SessionClient({fetchImpl:async()=>bad?unauthorized():ok(),onSessionChange:r=>events.push(r)});await c.connect('good');bad=true;await assert.rejects(c.connect('bad'),e=>e.status===401&&e.message.includes('올바른지'));assert.equal(c.token,'good');assert.equal(c.epoch,1);assert.deepEqual(events,['connected']);});
test('only the latest overlapping connection can commit',async()=>{const first=deferred();const c=new SessionClient({fetchImpl:async(path,o)=>o.headers.get('Authorization')==='Bearer first'?first.promise:ok()});const a=c.connect('first');await c.connect('second');first.resolve(ok());await assert.rejects(a,SessionCancelled);assert.equal(c.token,'second');});
test('disconnect during a connection probe prevents a late login',async()=>{const d=deferred();const c=new SessionClient({fetchImpl:()=>d.promise});const p=c.connect('candidate');c.disconnect();d.resolve(ok());await assert.rejects(p,SessionCancelled);assert.equal(c.token,'');});
test('old 401 after new connection cannot invalidate new session',async()=>{const d=deferred();const c=new SessionClient({fetchImpl:async path=>path.endsWith('/features')?ok():d.promise});await c.connect('one');const old=c.request('jobs');await c.connect('two');d.resolve(unauthorized());await assert.rejects(old,SessionCancelled);assert.equal(c.token,'two');});
test('reconnecting with the same token invalidates old request bodies',async()=>{const body=deferred();const c=new SessionClient({fetchImpl:async path=>path.endsWith('/features')?ok():{ok:true,status:200,json:()=>body.promise}});await c.connect('same');const pending=c.request('jobs');await Promise.resolve();await c.connect('same');body.resolve({jobs:['old']});await assert.rejects(pending,SessionCancelled);assert.equal(c.epoch,2);});
test('download 401 uses the same authentication handling',async()=>{const events=[];const c=new SessionClient({fetchImpl:async path=>path.endsWith('/features')?ok():unauthorized(),onSessionChange:r=>events.push(r)});await c.connect('one');await assert.rejects(c.request('jobs/x/downloads/a',{},'blob'),ApiError);assert.equal(c.token,'');assert.equal(events.at(-1),'unauthenticated');});
test('old download bytes cannot be used after session change',async()=>{const d=deferred();const c=new SessionClient({fetchImpl:async path=>path.endsWith('/features')?ok():{ok:true,status:200,blob:()=>d.promise}});await c.connect('one');const download=c.request('jobs/x/downloads/a',{},'blob');await Promise.resolve();await c.connect('two');d.resolve(new Blob(['private']));await assert.rejects(download,SessionCancelled);});
test('session timers are canceled even when reconnecting with same token',async()=>{let ran=0;const c=new SessionClient({fetchImpl:async()=>ok()});await c.connect('same');c.setTimer(()=>ran++,15);await c.connect('same');await wait(30);assert.equal(ran,0);});
test('active requests are aborted on session change',async()=>{let signal;const c=new SessionClient({fetchImpl:async(path,o)=>{if(path.endsWith('/features'))return ok();signal=o.signal;return new Promise(()=>{});}});await c.connect('one');void c.request('jobs');c.disconnect();assert.equal(signal.aborted,true);});
test('late logout response never changes a newer connection',async()=>{const d=deferred();let revokedToken;const c=new SessionClient({fetchImpl:async(path,o)=>{if(path.endsWith('/logout')){revokedToken=o.headers.get('Authorization');return d.promise;}return ok();}});await c.connect('one');const p=c.logout();await c.connect('two');d.resolve(unauthorized());await assert.rejects(p,SessionCancelled);assert.equal(revokedToken,'Bearer one');assert.equal(c.token,'two');});
test('failed remote logout reports uncertainty and clears local credentials',async()=>{const c=new SessionClient({fetchImpl:async path=>{if(path.endsWith('/logout'))throw Error('network');return ok();}});await c.connect('one');await assert.rejects(c.logout(),e=>e.message.includes('확인하지 못했습니다'));assert.equal(c.token,'');});
test('headers and no-store are consistent for all requests',async()=>{let options;const c=new SessionClient({fetchImpl:async(path,o)=>{options=o;return path.endsWith('/features')?ok():new Response(null,{status:204});}});await c.connect('good');await c.request('jobs',{headers:{Authorization:'Bearer wrong','X-Test':'yes'}});assert.equal(options.headers.get('Authorization'),'Bearer good');assert.equal(options.headers.get('X-Test'),'yes');assert.equal(options.cache,'no-store');assert.equal(options.redirect,'error');});

test('demo uses an HttpOnly cookie session without a bearer token',async()=>{
    const calls=[];const c=new SessionClient({fetchImpl:async(path,options)=>{calls.push({path,options});return ok();}});
    await c.connectDemo();await c.request('jobs',{method:'POST'});
    assert.equal(calls[0].path,'/demo/session');assert.equal(calls[0].options.headers['X-Audit-Request'],'1');
    assert.equal(calls.at(-1).options.headers.get('Authorization'),null);
    assert.equal(calls.at(-1).options.headers.get('X-Audit-Request'),'1');
});
test('disconnect prevents a late demo connection',async()=>{
    const response=deferred();const c=new SessionClient({fetchImpl:()=>response.promise});
    const pending=c.connectDemo();c.disconnect();response.resolve(ok());
    await assert.rejects(pending,SessionCancelled);assert.equal(c.token,'');
});
