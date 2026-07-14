from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect
import urllib.request
import json
import os
import io # [신규 추가: 앨범 다중 파일 업로드를 위한 모듈]

# --- [수정: 구글 API 연동을 위한 필수 모듈 (OAuth 2.0 사용자 로그인 방식)] ---
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload 
# ------------------------------------------------

app = Flask(__name__)
# [신규 추가] Vercel 서버리스 환경에서 로그인 세션 유지를 위한 고정 암호키 설정
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "line7-mech-c-super-secret-key") 
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
# [수정] 구글 드라이브 OAuth 2.0 사용자 인증 및 로그인 라우터 설정
# ==============================================================================
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_flow():
    """환경변수에 등록된 OAuth 정보를 바탕으로 인증 흐름(Flow) 객체를 생성합니다."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")
    
    client_config = {
        "web": {
            "client_id": client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [redirect_uri]
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    return flow

@app.route('/auth/login')
def login():
    """사용자가 이 주소로 접속하면 구글 로그인 화면으로 보냅니다."""
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """구글 로그인 성공 후, 구글 서버가 이 주소로 토큰(인증키)을 들고 돌아옵니다."""
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # 로컬 테스트용
    flow = get_flow()
    
    # Vercel 환경에서 콜백 URL이 http로 잡히는 오류를 방지
    auth_response = request.url.replace('http://', 'https://')
    flow.fetch_token(authorization_response=auth_response)
    
    # 발급받은 인증키를 브라우저 세션에 안전하게 저장
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return redirect('/') # 로그인 처리가 끝나면 메인 화면으로 자동 이동

def get_drive_service():
    """세션에 저장된 토큰을 꺼내서 드라이브 통신용 객체를 만듭니다."""
    if 'credentials' not in session:
        raise Exception("AUTH_REQUIRED") # 로그인이 안 되어 있으면 에러 발생
    
    creds_data = session['credentials']
    creds = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data.get('token_uri'),
        client_id=creds_data.get('client_id'),
        client_secret=creds_data.get('client_secret'),
        scopes=creds_data.get('scopes')
    )
    return build('drive', 'v3', credentials=creds)

# ==============================================================================
# [수정] 구글 드라이브 특정 폴더의 파일 및 폴더 목록 호출 API (앨범 전용)
# ==============================================================================
@app.route('/api/drive/files', methods=['POST'])
def get_drive_files():
    folder_type = request.json.get('folder_type') 
    
    if folder_type == 'album':
        folder_id = os.environ.get('DRIVE_FOLDER_ALBUM')
    else:
        folder_id = request.json.get('folder_id')
        
    if not folder_id:
        return jsonify({"status": "error", "message": "Missing folder ID"}), 400
        
    try:
        service = get_drive_service()
        
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query, 
            fields="nextPageToken, files(id, name, mimeType, webViewLink, thumbnailLink, createdTime, modifiedTime)", 
            pageSize=100,
            orderBy="folder, modifiedTime desc" 
        ).execute()
        
        files = results.get('files', [])
        return jsonify({"status": "success", "data": files})
    except Exception as e:
        # 로그인 정보가 없을 경우 프론트엔드에 별도 신호 전송
        if str(e) == "AUTH_REQUIRED":
            return jsonify({"status": "auth_required", "message": "구글 로그인이 필요합니다."}), 401
        print(f"Drive API Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================================================================
# [수정] 구글 드라이브 앨범 폴더 생성 및 다중 파일 업로드 API
# ==============================================================================
@app.route('/api/drive/upload', methods=['POST'])
def upload_drive_files():
    folder_name = request.form.get('folder_name') 
    files = request.files.getlist('files') 
    
    album_root_id = os.environ.get('DRIVE_FOLDER_ALBUM')
    
    if not folder_name or not album_root_id:
        return jsonify({"status": "error", "message": "Missing folder info"}), 400
        
    try:
        service = get_drive_service()
        
        query = f"name = '{folder_name}' and '{album_root_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        found_folders = results.get('files', [])
        
        if not found_folders:
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [album_root_id]
            }
            target_folder = service.files().create(body=folder_metadata, fields='id').execute()
            target_folder_id = target_folder.get('id')
        else:
            target_folder_id = found_folders[0].get('id')
        
        uploaded_files = []
        for f in files:
            if f.filename == '':
                continue
                
            file_metadata = {
                'name': f.filename,
                'parents': [target_folder_id]
            }
            
            media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype=f.mimetype, resumable=True)
            
            uploaded_file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
            uploaded_files.append(uploaded_file)
            
        return jsonify({"status": "success", "message": f"{len(uploaded_files)}개 파일 업로드 완료"})
    except Exception as e:
        if str(e) == "AUTH_REQUIRED":
            return jsonify({"status": "auth_required", "message": "구글 로그인이 필요합니다."}), 401
        print(f"Upload Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================================================================
# [유지] 수파베이스 스토리지(자료실) 파일 목록 호출 API
# ==============================================================================
@app.route('/api/storage/files', methods=['POST'])
def get_storage_files():
    bucket_name = 'docs' 
    url = f"{os.environ.get('SUPABASE_URL')}/storage/v1/object/list/{bucket_name}"
    
    payload = {
        "prefix": "",
        "limit": 100,
        "offset": 0,
        "sortBy": {"column": "created_at", "order": "desc"}
    }
    
    req = urllib.request.Request(url, headers=get_headers(), method='POST')
    req.data = json.dumps(payload).encode('utf-8')
    
    try:
        with urllib.request.urlopen(req) as res:
            files_data = json.loads(res.read().decode('utf-8'))
            
            formatted_files = []
            for f in files_data:
                if f['name'] == '.emptyFolderPlaceholder': continue
                
                public_url = f"{os.environ.get('SUPABASE_URL')}/storage/v1/object/public/{bucket_name}/{f['name']}"
                
                formatted_files.append({
                    "id": f["id"],
                    "name": f["name"],
                    "mimeType": f["metadata"]["mimetype"],
                    "webViewLink": public_url,
                    "thumbnailLink": public_url if "image" in f["metadata"]["mimetype"] else None,
                    "modifiedTime": f["updated_at"]
                })
            
            return jsonify({"status": "success", "data": formatted_files})
    except Exception as e:
        print(f"Storage API Error: {e}")
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
