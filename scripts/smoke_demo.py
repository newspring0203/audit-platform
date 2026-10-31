"""Exercise the real deployed HTTPS origin; credentials remain in memory."""
import argparse, io, json, time, zipfile
from urllib.parse import urlsplit
import httpx

def check(base):
    parsed=urlsplit(base)
    if parsed.scheme!='https' or not parsed.netloc or parsed.path not in {'','/'} or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('Provide the HTTPS origin only')
    base=base.rstrip('/')
    headers={'Origin':base,'X-Audit-Request':'1'}
    results=[]
    with httpx.Client(base_url=base,timeout=90,follow_redirects=False,headers=headers) as client, httpx.Client(base_url=base,timeout=90,headers=headers) as other:
        response=client.get('/health');response.raise_for_status()
        info=client.get('/deployment-info');info.raise_for_status()
        assert info.json()['mode']=='demo','Expected public demo mode'
        assert client.get('/api/features').status_code==401
        assert client.post('/demo/session',headers={'Origin':'https://invalid.example','X-Audit-Request':'1'}).status_code==403
        response=client.post('/demo/session');response.raise_for_status()
        assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
        other.post('/demo/session').raise_for_status()
        for module in info.json()['demo_modules']:
            response=client.post('/api/jobs',json={'module':module,'parameters':{}});response.raise_for_status()
            job=response.json();path='/api/jobs/'+job['job_id']
            try:
                assert other.get(path).status_code==404,'Visitor isolation failed'
                assert client.put(path+'/inputs/gl',content=b'not-an-accepted-upload').status_code==403
                client.post(path+'/run').raise_for_status()
                deadline=time.monotonic()+150
                while time.monotonic()<deadline:
                    response=client.get(path);response.raise_for_status();job=response.json()
                    if job['status']=='completed':break
                    time.sleep(1)
                assert job['status']=='completed','Analysis timeout'
                response=client.get(path+'/review');response.raise_for_status();summary=response.json()['summary']
                download=path+'/downloads/'+job['artifact']['artifact_id']
                assert other.get(download).status_code==404
                response=client.get(download);response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
                    assert bundle.testzip() is None
                    assert 'review/analysis/summary.json' in bundle.namelist()
                    assert 'review/processing_issue.json' not in bundle.namelist()
                results.append({'module':module,'status':'passed','zip_bytes':len(response.content),'summary':summary})
            finally:
                client.delete(path).raise_for_status()
        assert client.post('/api/jobs',json={'module':'kyc','parameters':{}}).status_code==403
        client.post('/api/logout').raise_for_status()
        assert client.get('/api/features').status_code==401
        other.post('/api/logout').raise_for_status()
    return {'base_url':base,'checked_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'checks':results,'isolation':'passed','csrf':'passed','uploads':'blocked','external_api':'blocked','logout':'passed'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('base_url');args=parser.parse_args()
    print(json.dumps(check(args.base_url),ensure_ascii=False,indent=2))
