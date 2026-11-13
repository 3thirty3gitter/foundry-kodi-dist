"""Profile-local provider cache and cross-interpreter request leases.

Kodi starts the service and RunScript windows in separate Python interpreters.
SQLite, rather than a module singleton alone, coordinates their HTTP work.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid


class MetadataCache:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (provider TEXT, owner TEXT, item TEXT, payload TEXT, expires REAL, stale REAL, PRIMARY KEY(provider,owner,item))')
            db.execute('CREATE TABLE IF NOT EXISTS metadata_blocks (provider TEXT, owner TEXT, status TEXT, expires REAL, PRIMARY KEY(provider,owner))')
            db.execute('CREATE TABLE IF NOT EXISTS metadata_leases (provider TEXT, owner TEXT, item TEXT, token TEXT, expires REAL, PRIMARY KEY(provider,owner,item))')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, provider, owner, item, stale=False):
        with self.connect() as db:
            row = db.execute('SELECT payload,expires,stale FROM metadata WHERE provider=? AND owner=? AND item=?', (provider,owner,item)).fetchone()
        if row and self.clock() < row[2 if stale else 1]:
            try:
                data = json.loads(row[0])
                return data if isinstance(data,dict) else None
            except (ValueError,TypeError):
                pass
        return None

    def put(self, provider, owner, item, payload, ttl=7*86400):
        now = self.clock()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?,?,?,?,?)', (provider,owner,item,json.dumps(payload),now+ttl,now+(30*86400 if payload else ttl)))
            db.execute('DELETE FROM metadata WHERE stale < ?', (now,))
            db.execute('DELETE FROM metadata WHERE rowid IN (SELECT rowid FROM metadata ORDER BY expires DESC LIMIT -1 OFFSET 5000)')

    def blocked(self, provider, owner):
        with self.connect() as db:
            row = db.execute('SELECT status,expires FROM metadata_blocks WHERE provider=? AND owner=?', (provider,owner)).fetchone()
        return row[0] if row and row[1] > self.clock() else ''

    def block(self, provider, owner, status, seconds):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO metadata_blocks VALUES (?,?,?,?)', (provider,owner,status,self.clock()+max(30,min(86400,seconds))))

    def claim(self, provider, owner, item):
        token = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM metadata_leases WHERE expires < ?', (self.clock(),))
            # Bound concurrent lookups across the service and all catalog windows.
            if db.execute('SELECT COUNT(*) FROM metadata_leases').fetchone()[0] >= 2:
                return ''
            try:
                db.execute('INSERT INTO metadata_leases VALUES (?,?,?,?,?)', (provider,owner,item,token,self.clock()+120))
            except sqlite3.IntegrityError:
                return ''
        return token

    def release(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM metadata_leases WHERE token=?', (token,))

    def clear(self):
        with self.connect() as db:
            # Active HTTP work still owns its slot until completion/lease expiry.
            for table in ('metadata','metadata_blocks'):
                db.execute('DELETE FROM '+table)
