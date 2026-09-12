"""Loopback-only HTTP checks: authenticated requests never follow redirects."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

spec=importlib.util.spec_from_file_location('runtime',Path(__file__).parents[1]/'worker/runtime.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
destinations=[]
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):self.reply()
    def do_POST(self):self.reply()
    def reply(self):
        if self.path=='/destination':
            destinations.append(self.headers)
            self.send_response(200);self.end_headers();self.wfile.write(b'{}')
        else:
            self.send_response(int(self.path[1:]));self.send_header('Location','http://127.0.0.1:'+str(self.server.server_port)+'/destination');self.end_headers()
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    for method in ['GET','POST']:
        for code in [302,307]:
            try:
                runtime.http('http://127.0.0.1:'+str(server.server_port)+'/'+str(code),method=method,headers={'Authorization':'Bearer fixture-app-key','OAI-Sites-Authorization':'Bearer fixture-sites-key'},body={} if method=='POST' else None)
                raise AssertionError('Redirect unexpectedly succeeded')
            except runtime.RuntimeFailure:print('PASS',method,code,'redirect refused')
    assert not destinations,'Credentials reached redirect destination'
    print('PASS No authenticated request reached the redirect destination')
finally:
    server.shutdown();thread.join(timeout=5);server.server_close()
print('5 local machine-credential HTTP checks passed.')
