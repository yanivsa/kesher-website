"""Authenticated service endpoint for a single cutover invocation.

The durable invocation ledger prevents replay of the same live Actions attempt.
It is ONLY a deny ledger, never exclusion evidence or canonical state. Native
resource observers, independent approval and the original Git journal remain
mandatory. The server accepts no provider/state/evidence material from clients.
"""
import argparse
import copy
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

    def check(self):
        """Read-only storage/schema check; cannot initialize a missing ledger."""
        try:
            with closing(sqlite3.connect(Path(self.path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
                columns=[(r[1],r[2],r[3],r[5]) for r in db.execute('PRAGMA table_info(invocations)')]
                if (db.execute('PRAGMA quick_check').fetchall()!=[('ok',)] or
                        columns!=[('epoch','TEXT',1,1),('run','TEXT',1,2)]):
                    raise sqlite3.DatabaseError()
        except (OSError,sqlite3.Error):
            raise StateInvalid('CUTOVER_LEDGER_UNAVAILABLE') from None

    def claim(self, epoch, run):
        try:
            # Missing storage fails closed; never silently initialize after loss.
            with closing(sqlite3.connect(Path(self.path).resolve().as_uri()+'?mode=rw',uri=True)) as db, db:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO invocations(epoch,run) VALUES (?,?)',(epoch,run))
        except sqlite3.Error:
            raise StateInvalid('CUTOVER_INVOCATION_REPLAY_OR_LEDGER_UNAVAILABLE') from None


class CutoverApplication:
    def __init__(self, *, runtime, identity, journal, epoch, reviewed_revision, review_check, installation=None):
        self.runtime,self.identity,self.journal=runtime,identity,journal
        self.epoch,self.reviewed_revision=epoch,reviewed_revision
        self.review_check=review_check
        self.installation=copy.deepcopy(installation)

    def preflight(self):
        from .cutover_installation import validate_installation
        validate_installation(self)
        self.review_check()
        return self.runtime.preflight()

    def step(self, token, request):
        if request != {'epoch':self.epoch,'reviewed_revision':self.reviewed_revision}:
            raise StateInvalid('CUTOVER_EPOCH_REVISION_BINDING_REQUIRED')
        self.review_check()  # actual gateway bytes/independent review, not client claims
        run=self.identity.verify(token)
        self.journal.claim(self.epoch,run)  # durable before ANY mutation
        return self.runtime.step()


def handler(application):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, *args): pass  # Authorization/payload never logged

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
    parser.add_argument('--factory-root',required=True,help='Independent absolute factory directory')
    parser.add_argument('--factory-sha256',required=True,help='Independently reviewed factory digest')
    parser.add_argument('--check-only',action='store_true',help='Read-only preflight; never step or serve')
    parser.add_argument('--port',type=int,default=8789)
    args=parser.parse_args(argv)
    from .cutover_installation import load_factory
    application=load_factory(args.factory,args.factory_root,args.factory_sha256)()
    if not isinstance(application,CutoverApplication): raise StateInvalid('CUTOVER_TRUSTED_APPLICATION_REQUIRED')
    application.preflight()
    if args.check_only: return 0
    # Bind loopback only. Administrator TLS ingress terminates at this server;
    # OIDC is verified independently here even if ingress has been compromised.
    HTTPServer(('127.0.0.1',args.port),handler(application)).serve_forever()


if __name__ == '__main__': main()
