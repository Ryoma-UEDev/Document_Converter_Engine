import http.server
import argparse
import json
import os
import urllib.parse

def get_roots():
    if os.name == 'nt':
        roots = []
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive = f'{letter}:\\'
            if os.path.exists(drive):
                roots.append(drive)
        return roots
    return ['/']

class DocumentHandler(http.server.SimpleHTTPRequestHandler):
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(url.query)
        
        if url.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            with open('index.html', 'rb') as f:
                self.wfile.write(f.read())
                
        elif url.path == '/api/browse':
            path = params.get('path', [''])[0] or os.getcwd()
            try:
                path = os.path.abspath(os.path.expanduser(path))
                items = os.listdir(path)
                dirs = [d for d in items if os.path.isdir(os.path.join(path, d))]
                res = {
                    'path': path,
                    'directories': sorted(dirs),
                    'parent': os.path.dirname(path) if path != os.path.dirname(path) else '',
                    'home': os.path.expanduser('~'),
                    'cwd': os.getcwd(),
                    'roots': get_roots(),
                    'separator': os.sep
                }
            except Exception as e:
                res = {'error': str(e), 'path': path, 'directories': [], 'parent': '', 'home': os.path.expanduser('~'), 'cwd': os.getcwd(), 'roots': get_roots(), 'separator': os.sep}
            self.send_json(res)

        elif url.path == '/api/pick-folder':
            start_path = params.get('path', [''])[0] or os.getcwd()
            if not os.path.isdir(start_path):
                start_path = os.getcwd()
            try:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                selected = filedialog.askdirectory(initialdir=start_path, title='Select folder')
                root.destroy()
                self.send_json({'path': os.path.abspath(selected) if selected else '', 'cancelled': not bool(selected)})
            except Exception as e:
                self.send_json({'error': str(e), 'path': '', 'cancelled': False}, status=500)
            
        elif url.path == '/api/scan':
            inp_dir = params.get('input', [''])[0]
            out_dir = params.get('output', [''])[0]
            pairs = []
            if os.path.exists(inp_dir) and os.path.exists(out_dir):
                try:
                    inp_files = {os.path.splitext(f)[0].lower(): f for f in os.listdir(inp_dir) if os.path.splitext(f)[1].lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.webp']}
                    out_files = {os.path.splitext(f)[0].lower(): f for f in os.listdir(out_dir) if os.path.splitext(f)[1].lower() == '.json'}
                    for k in sorted(inp_files.keys()):
                        if k in out_files:
                            pairs.append({
                                'name': os.path.splitext(inp_files[k])[0],
                                'input_path': os.path.join(inp_dir, inp_files[k]),
                                'output_path': os.path.join(out_dir, out_files[k])
                            })
                except Exception as e:
                    pass
            self.send_json({'pairs': pairs})
            
        elif url.path == '/api/file':
            file_path = params.get('path', [''])[0]
            if file_path and os.path.exists(file_path):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                if file_path.lower().endswith('.pdf'):
                    self.send_header('Content-Type', 'application/pdf')
                elif file_path.lower().endswith('.json'):
                    self.send_header('Content-Type', 'application/json')
                else:
                    self.send_header('Content-Type', 'image/octet-stream')
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File Not Found")
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/save':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            file_path = data.get('path')
            content = data.get('content')
            if file_path and content is not None:
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                    self.send_json({'status': 'ok'})
                except Exception as e:
                    self.send_json({'error': str(e)}, status=500)
            else:
                self.send_json({'error': 'Invalid arguments'}, status=400)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Result Review Bench local server')
    parser.add_argument('--port', type=int, default=8050)
    args = parser.parse_args()

    server_address = ('', args.port)
    httpd = http.server.HTTPServer(server_address, DocumentHandler)
    print(f"Serving on http://localhost:{args.port} ...")
    httpd.serve_forever()
