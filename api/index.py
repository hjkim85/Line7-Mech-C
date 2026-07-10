from flask import Flask, render_template, request, jsonify, send_from_directory
import urllib.request
import json
import os

# --- [신규 추가: 구글 API 연동을 위한 필수 모듈] ---
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
# ------------------------------------------------

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_headers():
    api_key = os.environ.get("SUPABASE_KEY")
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def db_request(table, method='GET', query="", data=None):
    url = f"{os.environ.get('SUPABASE_URL')}/rest/v1/{table}{query}"
    req = urllib.request.Request(url, headers=get_headers(), method=method)
    if data:
        req.data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req) as res:
            content = res.read()
            return json.loads(content.decode('utf-8')) if content else []
    except Exception as e:
        print(f"DB Error: {e}")
        return []

@app.route('/')
def home():
    return render_template('index.html')

# ==============================================================================
# [신규 추가] 구글 로그인 토큰 검증 API
# ==============================================================================
@app.route('/api/auth/verify', methods=['POST'])
def verify_google_token():
    token = request.json.get('token')
    client_id = os.environ.get("GOOGLE_CLIENT_ID") # Vercel 환경변수에 추가될 예정입니다.
    try:
        # 프론트엔드에서 보낸 id_token 검증
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')
        # 검증 성공 시 유저 정보 반환
        return jsonify({"status": "success", "user": {"email": idinfo['email'], "name": idinfo.get('name', '')}})
    except Exception as e:
        print(f"Token Auth Error: {e}")
        return jsonify({"status": "error", "message": "Invalid token"}), 401

# ==============================================================================
# [신규 추가] 구글 드라이브 특정 폴더 파일 목록 호출 API
# ==============================================================================
@app.route('/api/drive/files', methods=['POST'])
def get_drive_files():
    access_token = request.json.get('access_token')
    folder_id = request.json.get('folder_id') # 조회할 구글 드라이브 폴더 ID (자료실 또는 앨범)
    
    if not access_token or not folder_id:
        return jsonify({"status": "error", "message": "Missing token or folder ID"}), 400
        
    try:
        # 프론트엔드에서 넘어온 액세스 토큰으로 권한 증명 생성
        creds = Credentials(token=access_token)
        service = build('drive', 'v3', credentials=creds)
        
        # 지정된 폴더 내의 파일 검색 (휴지통 제외)
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query, 
            fields="nextPageToken, files(id, name, mimeType, webViewLink, thumbnailLink, createdTime)", 
            pageSize=100
        ).execute()
        
        files = results.get('files', [])
        return jsonify({"status": "success", "data": files})
    except Exception as e:
        print(f"Drive API Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 만능 데이터 호출 API (조회/생성)
@app.route('/api/<table>', methods=['GET', 'POST'])
def handle_table(table):
    if request.method == 'GET':
        query = "?order=created_at.desc"
        if table == 'tasks': query = "?order=start_date.desc"
        if table == 'events': query = "?order=event_date.desc"
        if table == 'event_comments': query = "?order=created_at.asc"
        return jsonify({"status": "success", "data": db_request(table, 'GET', query)})
    elif request.method == 'POST':
        return jsonify({"status": "success", "data": db_request(table, 'POST', "", request.json)})

# 만능 데이터 수정 API (수정/삭제)
@app.route('/api/<table>/<int:item_id>', methods=['PATCH', 'DELETE'])
def handle_item(table, item_id):
    if request.method == 'PATCH':
        return jsonify({"status": "success", "data": db_request(table, 'PATCH', f"?id=eq.{item_id}", request.json)})
    elif request.method == 'DELETE':
        return jsonify({"status": "success", "data": db_request(table, 'DELETE', f"?id=eq.{item_id}")})

@app.route('/icon.png')
def serve_icon(): return send_from_directory(BASE_DIR, 'icon.png', mimetype='image/png')
@app.route('/manifest.json')
def serve_manifest(): return send_from_directory(BASE_DIR, 'manifest.json', mimetype='application/json')

if __name__ == '__main__':
    app.run()
