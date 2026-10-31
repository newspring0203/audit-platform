"""Read only requested review rows; keep the complete snapshot in the ZIP."""
from contextlib import closing
import json
import sqlite3


def write_index(folder, manifest, frames):
    with closing(sqlite3.connect(folder / 'review_index.sqlite')) as db:
        db.executescript('CREATE TABLE entries (kind TEXT, name TEXT, position INTEGER, payload TEXT, PRIMARY KEY(kind,name,position));')
        def put(kind, name, position, value):
            db.execute('INSERT INTO entries VALUES(?,?,?,?)', (kind,name,position,json.dumps(value,ensure_ascii=False,allow_nan=False)))
        overview={k:v for k,v in manifest.items() if k not in {'tables','trace'}}
        overview['tables']={k:{'columns':v['columns'],'row_count':v['row_count']} for k,v in manifest['tables'].items()}
        put('overview','',0,overview)
        for name, table in manifest['tables'].items():
            for pos,row in enumerate(table['rows']): put('table',name,pos,row)
        for key,entry in manifest['trace'].items(): put('trace',key,0,entry)
        for slot,frame in frames.items():
            for start in range(0,len(frame),1000):
                rows=json.loads(frame.iloc[start:start+1000].to_json(orient='records',date_format='iso',force_ascii=False))
                for pos,row in enumerate(rows,start): put('source',slot,pos,row)
        db.commit()


def read_one(folder, kind, name, position=0):
    with closing(sqlite3.connect(f'file:{folder / "review_index.sqlite"}?mode=ro',uri=True)) as db:
        row=db.execute('SELECT payload FROM entries WHERE kind=? AND name=? AND position=?',(kind,name,position)).fetchone()
    return json.loads(row[0]) if row else None


class Rows:
    def __init__(self,folder,name): self.folder=folder;self.name=name
    def __getitem__(self,key):
        if isinstance(key,slice):
            with closing(sqlite3.connect(f'file:{self.folder / "review_index.sqlite"}?mode=ro',uri=True)) as db:
                rows=db.execute('SELECT payload FROM entries WHERE kind=? AND name=? AND position>=? AND position<? ORDER BY position',('table',self.name,key.start or 0,key.stop)).fetchall()
            return [json.loads(row[0]) for row in rows]
        return read_one(self.folder,'table',self.name,key)


class Traces:
    def __init__(self,folder): self.folder=folder
    def get(self,key,default=None):
        value=read_one(self.folder,'trace',key)
        return default if value is None else value
    def __contains__(self,key): return self.get(key) is not None


def snapshot(folder):
    data=read_one(folder,'overview','')
    for name,table in data['tables'].items(): table['rows']=Rows(folder,name)
    data['trace']=Traces(folder)
    return data
