#!/usr/bin/env python3
"""
포트폴리오 통합 웹 호스팅 & portfolio.md 실시간 자동 동기화 서버
- 전세계 어디서나 접속 가능 (Cloudflare Tunnel HTTPS 자동 연동, LTE/5G 지원)
- 모바일, 태블릿, 다른 PC 등 로컬 네트워크(동일 Wi-Fi) 접속 지원 (0.0.0.0 바인딩)
- 웹사이트 정적 파일 서빙 (index.html, CSV, 폰트 에셋 등)
- 실시간 HTML <-> portfolio.md 마크다운 동기화 처리
"""

import os
import sys
import re
import json
import socket
import mimetypes
import threading
import subprocess
from urllib.parse import urlparse, unquote
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8765
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MD_PATH = os.path.join(CURRENT_DIR, 'portfolio.md')
CLOUDFLARED_PATH = os.path.join(CURRENT_DIR, 'bin', 'cloudflared')

PUBLIC_URL = None
tunnel_process = None

def get_local_ip():
    """로컬 네트워크 IP 주소 자동 감지"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            out = subprocess.check_output(['ipconfig', 'getifaddr', 'en0'], text=True).strip()
            if out:
                return out
        except Exception:
            pass
        return '127.0.0.1'

LOCAL_IP = get_local_ip()

def start_cloudflared_tunnel():
    """Cloudflare Tunnel을 백그라운드로 실행하여 외부 공개 HTTPS URL 생성"""
    global PUBLIC_URL, tunnel_process
    
    bin_path = CLOUDFLARED_PATH if os.path.exists(CLOUDFLARED_PATH) else '/tmp/cloudflared'
    if not os.path.exists(bin_path):
        print("[터널 알림] cloudflared 바이너리를 찾을 수 없어 로컬 네트워크 모드로만 동작합니다.")
        return

    try:
        cmd = [bin_path, 'tunnel', '--url', f'http://127.0.0.1:{PORT}']
        tunnel_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        print("🌐 [Cloudflare Tunnel] 외부 접속용 보안 터널을 생성 중입니다...")

        for line in iter(tunnel_process.stdout.readline, ''):
            if not line:
                break
            # trycloudflare.com URL 감지
            m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if m:
                PUBLIC_URL = m.group(0)
                print("=" * 64)
                print(f"🎉 [전세계 공개 HTTPS 접속 링크 발급 완료!]")
                print(f"🔗 외부 접속 URL (LTE/5G/어디서나): {PUBLIC_URL}")
                print("=" * 64)
    except Exception as e:
        print(f"[터널 오류] {e}", file=sys.stderr)

def run_git_sync(commit_msg="sync: auto deployment to GitHub Pages"):
    """로컬 변경사항(사진, portfolio.md, HTML 등)을 GitHub Pages로 즉시 커밋 & 푸시"""
    try:
        subprocess.run(['git', 'add', '-A'], cwd=CURRENT_DIR, check=True)
        diff = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=CURRENT_DIR)
        if diff.returncode != 0:
            subprocess.run(['git', 'commit', '-m', commit_msg], cwd=CURRENT_DIR, check=True)
            res = subprocess.run(['git', 'push', 'origin', 'main'], cwd=CURRENT_DIR, text=True, capture_output=True)
            if res.returncode == 0:
                print(f"🚀 [GitHub 자동 배포 성공] {commit_msg}")
                return True
            else:
                print(f"[GitHub 푸시 실패] {res.stderr}", file=sys.stderr)
                return False
        else:
            print("[GitHub 동기화] 최신 커밋과 변경 사항이 없습니다 (이미 최신 반영됨).")
            return True
    except Exception as e:
        print(f"[GitHub 배포 실행 오류] {e}", file=sys.stderr)
        return False

class IntegratedPortfolioHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # 1. 서버 상태 및 접속 주소 반환 API (로컬 IP + 외부 공개 URL 모두 제공)
        if path == '/status':
            self._set_headers(200, 'application/json; charset=utf-8')
            resp = {
                "status": "running",
                "target_file": "portfolio.md",
                "local_ip": LOCAL_IP,
                "port": PORT,
                "access_url": f"http://{LOCAL_IP}:{PORT}",
                "public_url": PUBLIC_URL
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8'))
            return

        # 2. 루트 요청 시 index.html 서빙
        if path in ['/', '/index.html']:
            index_file = os.path.join(CURRENT_DIR, 'index.html')
            if os.path.exists(index_file):
                self._serve_file(index_file, 'text/html; charset=utf-8')
            else:
                self._send_error_page(404, "index.html 파일을 찾을 수 없습니다.")
            return

        # 3. 폰트 및 상위 카드뉴스 디렉토리 요청 매핑 (../카드뉴스 or /카드뉴스)
        if path.startswith('/카드뉴스/'):
            target_path = os.path.normpath(os.path.join(PARENT_DIR, path.lstrip('/')))
            if os.path.exists(target_path) and os.path.isfile(target_path):
                mime, _ = mimetypes.guess_type(target_path)
                self._serve_file(target_path, mime or 'application/octet-stream')
                return

        # 4. 현재 폴더 내 일반 정적 파일 서빙
        rel_path = path.lstrip('/')
        file_path = os.path.normpath(os.path.join(CURRENT_DIR, rel_path))

        # 보안: CURRENT_DIR 또는 PARENT_DIR 벗어나는 경로 차단
        if not (file_path.startswith(CURRENT_DIR) or file_path.startswith(PARENT_DIR)):
            self._send_error_page(403, "접근이 금지된 경로입니다.")
            return

        if os.path.exists(file_path) and os.path.isfile(file_path):
            mime, _ = mimetypes.guess_type(file_path)
            if file_path.endswith('.css'):
                mime = 'text/css; charset=utf-8'
            elif file_path.endswith('.js'):
                mime = 'application/javascript; charset=utf-8'
            elif file_path.endswith('.csv'):
                mime = 'text/csv; charset=utf-8'
            elif file_path.endswith('.md'):
                mime = 'text/markdown; charset=utf-8'
            self._serve_file(file_path, mime or 'application/octet-stream')
            return

        # 5. 파일을 찾지 못한 경우
        self._send_error_page(404, f"요청하신 파일({path})을 찾을 수 없습니다.")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == '/save-md':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                with open(MD_PATH, 'w', encoding='utf-8') as f:
                    f.write(post_data)
                
                print(f"[동기화 성공] portfolio.md 업데이트 완료 ({len(post_data):,} bytes)")
                threading.Thread(target=run_git_sync, args=("docs: update portfolio.md via web sync",)).start()
                self._set_headers(200, 'application/json; charset=utf-8')
                self.wfile.write(b'{"success": true, "message": "portfolio.md updated successfully"}')
            except Exception as e:
                print(f"[동기화 오류] {e}", file=sys.stderr)
                self._set_headers(500, 'application/json; charset=utf-8')
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
        elif path == '/upload-avatar':
            content_length = int(self.headers.get('Content-Length', 0))
            raw_data = self.rfile.read(content_length)
            try:
                import base64
                payload = json.loads(raw_data.decode('utf-8'))
                img_data = payload.get('image', '')
                if ',' in img_data:
                    img_data = img_data.split(',', 1)[1]
                img_bytes = base64.b64decode(img_data)
                
                avatar_path = os.path.join(CURRENT_DIR, 'assets', 'profile.jpg')
                with open(avatar_path, 'wb') as f:
                    f.write(img_bytes)
                
                print(f"[사진 동기화 성공] assets/profile.jpg 저장 완료 ({len(img_bytes):,} bytes)")
                # 깃허브 자동 푸시 스레드 실행
                threading.Thread(target=run_git_sync, args=("feat: update profile photo via web upload",)).start()
                self._set_headers(200, 'application/json; charset=utf-8')
                self.wfile.write(json.dumps({"success": True, "url": "assets/profile.jpg"}).encode('utf-8'))
            except Exception as e:
                print(f"[사진 업로드 오류] {e}", file=sys.stderr)
                self._set_headers(500, 'application/json; charset=utf-8')
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
        elif path == '/deploy-to-github':
            content_length = int(self.headers.get('Content-Length', 0))
            raw_data = self.rfile.read(content_length)
            try:
                payload = json.loads(raw_data.decode('utf-8'))
                img_data = payload.get('avatar', '')
                if img_data:
                    import base64
                    if ',' in img_data:
                        img_data = img_data.split(',', 1)[1]
                    img_bytes = base64.b64decode(img_data)
                    avatar_path = os.path.join(CURRENT_DIR, 'assets', 'profile.jpg')
                    with open(avatar_path, 'wb') as f:
                        f.write(img_bytes)
                    print(f"[배포] 프로필 사진 저장 완료 ({len(img_bytes):,} bytes)")

                md_data = payload.get('markdown', '')
                if md_data:
                    with open(MD_PATH, 'w', encoding='utf-8') as f:
                        f.write(md_data)
                    print(f"[배포] portfolio.md 갱신 완료 ({len(md_data):,} bytes)")

                # 동기식 또는 비동기식 깃 푸시 실행
                success = run_git_sync("sync: manual one-click deployment to GitHub Pages")
                self._set_headers(200, 'application/json; charset=utf-8')
                self.wfile.write(json.dumps({
                    "success": success,
                    "message": "깃허브(GitHub Pages)에 최신 사진과 스펙이 성공적으로 배포되었습니다!"
                }).encode('utf-8'))
            except Exception as e:
                print(f"[배포 오류] {e}", file=sys.stderr)
                self._set_headers(500, 'application/json; charset=utf-8')
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
        else:
            self._send_error_page(404, "Endpoint Not Found")

    def _serve_file(self, file_path, content_type):
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            self._set_headers(200, content_type)
            self.wfile.write(content)
        except Exception as e:
            self._send_error_page(500, f"파일 읽기 오류: {e}")

    def _send_error_page(self, code, msg):
        self._set_headers(code, 'application/json; charset=utf-8')
        resp = {"error": True, "code": code, "message": msg}
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8'))

def run_server():
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, IntegratedPortfolioHandler)
    access_url = f"http://{LOCAL_IP}:{PORT}"
    
    # Cloudflare Tunnel 백그라운드 스레드 가동
    t = threading.Thread(target=start_cloudflared_tunnel, daemon=True)
    t.start()

    print("=" * 64)
    print("🚀 배터리 엔지니어 포트폴리오 글로벌 & 로컬 멀티 웹 서버 가동!")
    print("=" * 64)
    print(f"📍 대상 디렉터리: {CURRENT_DIR}")
    print(f"💻 내 맥북(Localhost) 접속: http://127.0.0.1:{PORT}")
    print(f"🏠 동일 Wi-Fi 로컬 접속: {access_url}")
    print(f"🌐 외부 인터넷(LTE/5G) 접속: Cloudflare 터널 자동 연결 중...")
    print(f"🔄 portfolio.md 자동 동기화 엔드포인트: POST /save-md")
    print("=" * 64)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 안전하게 종료합니다.")
        if tunnel_process:
            try:
                tunnel_process.terminate()
            except Exception:
                pass
        httpd.server_close()

if __name__ == '__main__':
    run_server()
