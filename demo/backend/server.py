"""Loopback-only demo HTTP server. No source tree, credentials or runs are static assets."""
import argparse
import hmac
import json
import mimetypes
import secrets
import socket
import threading
import webbrowser
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .engine import Engine, PUBLIC
from .runtime import PROJECT_ROOT


class Server(ThreadingHTTPServer):
    allow_reuse_address=False
    daemon_threads=True
    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()


def make_server(engine, port=8770):
    sessions={};session_lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # Never log query strings, uploads or keys.
        def identity(self,create=False):
            cookie=SimpleCookie()
            try:cookie.load(self.headers.get('Cookie',''))
            except Exception:pass
            sid=cookie.get('cfm_id_session');sid=sid.value if sid else None
            with session_lock:
                if sid not in sessions:
                    if not create:return None
                    if len(sessions)>=100:raise ValueError('LOCAL_SESSION_LIMIT')
                    sid=secrets.token_urlsafe(32);sessions[sid]=secrets.token_urlsafe(32)
                    self.new_cookie=sid
                return sid
        def send(self,status,body,content_type='application/json; charset=utf-8',*,download=None):
            if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf8')
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if getattr(self,'new_cookie',None):self.send_header('Set-Cookie',f'cfm_id_session={self.new_cookie}; HttpOnly; SameSite=Strict; Path=/')
            if download:self.send_header('Content-Disposition',f'attachment; filename="{download}"')
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def safe_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def do_GET(self):
            if not self.safe_host():return self.send(403,{'error':'LOCALHOST_ONLY'})
            parsed=urlparse(self.path);path=parsed.path
            try:
                owner=self.identity(create=path=='/')
                if path=='/':return self.send(200,(PUBLIC/'index.html').read_bytes(),'text/html; charset=utf-8')
                if path in ('/app.js','/input-files.js','/style.css','/favicon.svg'):
                    mime={'/input-files.js':'text/javascript','/app.js':'text/javascript','/style.css':'text/css','/favicon.svg':'image/svg+xml'}[path]
                    return self.send(200,(PUBLIC/path[1:]).read_bytes(),mime+'; charset=utf-8')
                if path in ('/templates/network_nodes.csv','/templates/network_edges.csv'):
                    return self.send(200,(PUBLIC/path[1:]).read_bytes(),'text/csv; charset=utf-8')
                if not owner:return self.send(401,{'error':'OPEN_HOME_FIRST'})
                if path=='/api/health':return self.send(200,{**engine.health(owner),'csrf':sessions[owner]})
                if path=='/api/examples':return self.send(200,engine.examples)
                if path=='/api/run':return self.send(200,engine.view(owner,parse_qs(parsed.query)['id'][0]))
                if path=='/api/download':
                    args=parse_qs(parsed.query);run=engine.get(owner,args['id'][0]);name=args['name'][0]
                    if name not in run.artifacts:raise ValueError('ARTIFACT_NOT_FOUND')
                    return self.send(200,run.artifacts[name],download=name+'.json')
                return self.send(404,{'error':'NOT_FOUND'})
            except (ValueError,KeyError):return self.send(400,{'error':'INVALID_REQUEST'})
        def do_POST(self):
            owner=self.identity();origin=self.headers.get('Origin')
            expected=f'http://{self.headers.get("Host")}'
            if (not self.safe_host() or not owner or (origin and origin!=expected)
                or not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),sessions[owner])):
                return self.send(403,{'error':'LOCAL_SESSION_AND_CSRF_REQUIRED'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=29*1024*1024:raise ValueError('REQUEST_SIZE_LIMIT')
                if self.headers.get_content_type()!='application/json':raise ValueError('JSON_REQUIRED')
                value=json.loads(self.rfile.read(size))
                if not isinstance(value,dict):raise ValueError('JSON_OBJECT_REQUIRED')
                if self.path=='/api/credentials':
                    return self.send(200,engine.credential(owner,value['provider'],value.get('key','')))
                if self.path in ('/api/table-preview','/api/input-preview'):
                    # Local only, no credentials or model request required.
                    try:
                        if self.path=='/api/input-preview': result=engine.preview_uploads(owner,value)
                        else:
                            import base64
                            from cfm_id_llm.tabular_files import preview
                            result=preview(base64.b64decode(value['content'],validate=True),value['name'],value.get('sheet'),value.get('header_row',1))
                        return self.send(200,result)
                    except (ValueError,KeyError,TypeError) as exc:
                        from pydantic import ValidationError
                        msg='请填写完整的列对应、变量说明和结果类型。' if isinstance(exc,ValidationError) else str(exc)[:500]
                        return self.send(400,{'error':msg})
                if self.path=='/api/start':return self.send(202,{'id':engine.start(owner,value)})
                if self.path=='/api/action':
                    engine.action(owner,value['id'],value['action'],value.get('payload',{}));return self.send(202,{'id':value['id']})
                return self.send(404,{'error':'NOT_FOUND'})
            except (ValueError,KeyError,TypeError) as exc:
                # Parsing errors may contain document contents: return a small code only.
                message=str(exc) if isinstance(exc,ValueError) and str(exc).isupper() else 'INVALID_REQUEST'
                return self.send(400,{'error':message})
    return Server(('127.0.0.1',port),Handler)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8772)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--max-api-calls',type=int,default=20)
    args=parser.parse_args(argv)
    if not 1<=args.max_api_calls<=200:parser.error('max-api-calls must be 1..200')
    engine=Engine(PROJECT_ROOT/'outputs/web_runs',max_api_calls=args.max_api_calls)
    server=make_server(engine,args.port);url=f'http://127.0.0.1:{server.server_port}/'
    print('AUTOCFM_LIVE_READY '+url,flush=True)
    if not args.no_browser:threading.Timer(.5,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:engine.credentials.clear();server.server_close()


if __name__=='__main__':main()
