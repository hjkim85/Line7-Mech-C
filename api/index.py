from flask import Flask, render_template, request, jsonify, send_from_directory
import urllib.request
import json
import os

# --- [수정: 구글 API 연동을 위한 필수 모듈 (서비스 계정 마스터 열쇠 방식)] ---
from google.oauth2 import service_account
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
# [수정] 구글 드라이브 서비스 계정(마스터 열쇠) 인증 및 연동 설정
# ==============================================================================
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Vercel 환경변수에 저장된 JSON(마스터 열쇠)을 읽어와 드라이브 권한을 얻습니다."""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("Vercel 환경변수에 GOOGLE_CREDENTIALS가 없습니다.")
    
    # JSON 문자열을 파이썬 딕셔너리로 변환 후 권한 객체 생성
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

# ==============================================================================
# [수정] 구글 드라이브 특정 폴더의 파일 및 폴더 목록 호출 API (서버 직접 호출)
# ==============================================================================
@app.route('/api/drive/files', methods=['POST'])
def get_drive_files():
    # 프론트엔드에서는 'docs'(자료실) 또는 'album'(사진첩) 이라는 구분값만 보냅니다.
    folder_type = request.json.get('folder_type') 
    
    # 요청된 타입에 따라 환경변수에서 알맞은 폴더 ID를 꺼냅니다.
    if folder_type == 'docs':
        folder_id = os.environ.get('DRIVE_FOLDER_DOCS')
    elif folder_type == 'album':
        folder_id = os.environ.get('DRIVE_FOLDER_ALBUM')
    else:
        # 특정 하위 폴더 안으로 들어갈 때를 대비하여 직접 ID를 받을 수도 있게 둡니다.
        folder_id = request.json.get('folder_id')
        
    if not folder_id:
        return jsonify({"status": "error", "message": "Missing folder ID"}), 400
        
    try:
        service = get_drive_service()
        
        # 지정된 폴더 내의 파일/폴더 검색 (휴지통 제외)
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query, 
            # 파일 정보 외에 폴더 여부(mimeType) 및 마지막 수정일(modifiedTime)도 함께 가져옵니다.
            fields="nextPageToken, files(id, name, mimeType, webViewLink, thumbnailLink, createdTime, modifiedTime)", 
            pageSize=100,
            orderBy="folder, modifiedTime desc" # 폴더를 먼저 보여주고, 그 다음 최신 수정일 순으로 정렬
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
