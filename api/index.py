from flask import Flask, render_template, request, jsonify, send_from_directory
import urllib.request
import json
import os
import io # [신규 추가: 앨범 다중 파일 업로드를 위한 모듈]

# --- [수정: 구글 API 연동을 위한 필수 모듈 (서비스 계정 마스터 열쇠 방식)] ---
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload # [신규 추가: 구글 드라이브 파일 전송 모듈]
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
# [수정] 구글 드라이브 특정 폴더의 파일 및 폴더 목록 호출 API (앨범 전용)
# ==============================================================================
@app.route('/api/drive/files', methods=['POST'])
def get_drive_files():
    folder_type = request.json.get('folder_type') 
    
    # [수정] docs는 수파베이스로 분리되었으므로 album 로직만 남깁니다.
    if folder_type == 'album':
        folder_id = os.environ.get('DRIVE_FOLDER_ALBUM')
    else:
        folder_id = request.json.get('folder_id')
        
    if not folder_id:
        return jsonify({"status": "error", "message": "Missing folder ID"}), 400
        
    try:
        service = get_drive_service()
        
        # 지정된 폴더 내의 파일/폴더 검색 (휴지통 제외)
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
        print(f"Drive API Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================================================================
# [신규 추가] 구글 드라이브 앨범 폴더 생성 및 다중 파일 업로드 API
# ==============================================================================
@app.route('/api/drive/upload', methods=['POST'])
def upload_drive_files():
    folder_name = request.form.get('folder_name') # 이벤트 제목을 폴더 이름으로 사용
    files = request.files.getlist('files') # 첨부된 사진들
    
    album_root_id = os.environ.get('DRIVE_FOLDER_ALBUM')
    
    if not folder_name or not album_root_id:
        return jsonify({"status": "error", "message": "Missing folder info"}), 400
        
    try:
        service = get_drive_service()
        
        # 1. 앨범 루트 안에 동일한 이름의 폴더가 있는지 검색
        query = f"name = '{folder_name}' and '{album_root_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        found_folders = results.get('files', [])
        
        # 2. 폴더가 없으면 새로 생성
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
        
        # 3. 타겟 폴더에 사진 파일들 업로드
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
        print(f"Upload Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================================================================
# [신규 추가] 수파베이스 스토리지(자료실) 파일 목록 호출 API
# ==============================================================================
@app.route('/api/storage/files', methods=['POST'])
def get_storage_files():
    bucket_name = 'docs' # 방금 만든 수파베이스 버킷 이름
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
            
            # 구글 드라이브 응답과 동일한 형태로 포맷팅하여 프론트엔드 호환성 유지
            formatted_files = []
            for f in files_data:
                if f['name'] == '.emptyFolderPlaceholder': continue
                
                # 수파베이스 public URL 조합 공식
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
