"""Authenticated service endpoint for a single cutover invocation.

The durable invocation ledger prevents replay of the same live Actions attempt.
It is ONLY a deny ledger, never exclusion evidence or canonical state. Native
resource observers, independent approval and the original Git journal remain
mandatory. The server accepts no provider/state/evidence material from clients.
"""
import argparse
import importlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

from .state import StateInvalid


class InvocationJournal:
    def __init__(self, path):
        self.path = str(path)

    @staticmethod
    def initialize(path):
        # Administrator bootstrap only; an existing ledger is never overwritten.
        import os
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd)
        with closing(sqlite3.connect(str(path))) as db, db:
            db.execute('CREATE TABLE invocations (epoch TEXT NOT NULL, run TEXT NOT NULL, PRIMARY KEY(epoch,run))')

    def claim(self, epoch, run):
        self.inspect()
        try:
            # Missing storage fails closed; never silently initialize after loss.
            with closing(sqlite3.connect(Path(self.path).resolve().as_uri()+'?mode=rw',uri=True)) as db, db:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO invocations(epoch,run) VALUES (?,?)',(epoch,run))
        except sqlite3.Error:
            raise StateInvalid('CUTOVER_INVOCATION_REPLAY_OR_LEDGER_UNAVAILABLE') from None

    def inspect(self):
        """Read-only integrity/schema check; absence must never initialize storage."""
        path = Path(self.path)
        try:
            if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
                raise ValueError('protected persistent ledger required')
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
                if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]: raise ValueError('integrity')
                columns = db.execute('PRAGMA table_info(invocations)').fetchall()
                if [(r[1],r[2],r[3],r[5]) for r in columns] != [('epoch','TEXT',1,1),('run','TEXT',1,2)]:
                    raise ValueError('deny ledger schema')
                db.execute('SELECT epoch,run FROM invocations LIMIT 1').fetchall()
        except (OSError,ValueError,sqlite3.Error):
            raise StateInvalid('CUTOVER_INVOCATION_LEDGER_UNAVAILABLE') from None


class CutoverApplication:
    def __init__(self, *, runtime, identity, journal, epoch, reviewed_revision, review_check):
        self.runtime,self.identity,self.journal=runtime,identity,journal
        self.epoch,self.reviewed_revision=epoch,reviewed_revision
        self.review_check=review_check

    def step(self, token, request):
        if request != {'epoch':self.epoch,'reviewed_revision':self.reviewed_revision}:
            raise StateInvalid('CUTOVER_EPOCH_REVISION_BINDING_REQUIRED')
        run=self.identity.verify(token)
        self.review_check()  # actual gateway bytes/independent review, not client claims
        self.journal.claim(self.epoch,run)  # durable before ANY mutation
        return self.runtime.step()


def handler(application):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, *args): pass  # Authorization/payload never logged

        def do_GET(self):
            callback = {'/healthz':'health','/v1/authority':'authority'}.get(self.path)
            if callback is None or not callable(getattr(application,callback,None)):
                self.send_error(404); return
            try:
                if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length','0') != '0':
                    raise StateInvalid('CUTOVER_READ_ONLY_REQUEST_REQUIRED')
                if callback == 'authority':
                    authorization = self.headers.get('Authorization','')
                    if not authorization.startswith('Bearer '): raise StateInvalid('CUTOVER_AUTH_REQUIRED')
                    result = application.authority(authorization.removeprefix('Bearer '))
                else: result = application.health()
                payload=json.dumps(result).encode(); status=200
            except Exception:
                payload=b'{"status":"BLOCKED"}'; status=503
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers(); self.wfile.write(payload)

        def do_POST(self):
            if self.path != '/v1/cutover/step':
                self.send_error(404); return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096: raise StateInvalid('CUTOVER_INVALID_REQUEST')
                authorization=self.headers.get('Authorization','')
                if not authorization.startswith('Bearer '): raise StateInvalid('CUTOVER_AUTH_REQUIRED')
                from .github import _unique_object
                request=json.loads(self.rfile.read(length),object_pairs_hook=_unique_object)
                result=application.step(authorization.removeprefix('Bearer '),request)
                payload=json.dumps(result).encode(); status=200
            except Exception:
                # No exception text/tracebacks, credentials or sealed/plaintext
                # migration data enter HTTP bodies or access logs.
                payload=b'{"status":"BLOCKED","production_activated":false,"public_completion_inferred":false}'
                status=409
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
    return Handler


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory',required=True,help='Administrator-installed reviewed module:function')
    parser.add_argument('--port',type=int,default=8789)
    args=parser.parse_args(argv)
    module,name=args.factory.split(':',1)
    application=getattr(importlib.import_module(module),name)()
    if not isinstance(application,CutoverApplication): raise StateInvalid('CUTOVER_TRUSTED_APPLICATION_REQUIRED')
    # Bind loopback only. Administrator TLS ingress terminates at this server;
    # OIDC is verified independently here even if ingress has been compromised.
    HTTPServer(('127.0.0.1',args.port),handler(application)).serve_forever()


if __name__ == '__main__': main()
