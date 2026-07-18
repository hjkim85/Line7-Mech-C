from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect
import urllib.request
import json
import os
from datetime import timedelta # [신규 추가] 세션 유지 기간 설정을 위한 모듈

# --- [신규 추가: Cloudflare R2 통신을 위한 AWS S3 호환 모듈] ---
import boto3
from botocore.client import Config
import urllib.parse
# ------------------------------------------------

app = Flask(__name__)
# [신규 추가] 세션 유지 기간을 31일로 설정 (모바일 앱 껐다 켜도 유지)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)
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
# [신규 통합] Cloudflare R2 스토리지 클라이언트 생성 함수
# ==============================================================================
def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=os.environ.get('R2_ENDPOINT_URL'),
        aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY'),
        region_name='auto',
        config=Config(signature_version='s3v4')
    )

# ==============================================================================
# [신규 통합] R2 스토리지 파일 및 폴더 목록 호출 API (자료실/앨범 공용)
# ==============================================================================
@app.route('/api/r2/files', methods=['POST'])
def get_r2_files():
    prefix = request.json.get('prefix', '') # 예: 'docs/', 'album/' 또는 'album/이벤트명/'
    bucket = os.environ.get('R2_BUCKET_NAME')
    
    try:
        s3 = get_r2_client()
        # Delimiter='/' 옵션을 주면 R2가 알아서 '폴더'와 '파일'을 구분해서 결과를 반환합니다.
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter='/')
        files_data = []
        
        # 1. 하위 폴더 목록 추출
        if 'CommonPrefixes' in response:
            for cp in response['CommonPrefixes']:
                folder_name = cp['Prefix'].replace(prefix, '').strip('/')
                files_data.append({
                    "id": cp['Prefix'], # 다음 탐색을 위한 경로 자체를 ID로 사용
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder", # 프론트엔드 호환성 유지
                    "webViewLink": "#"
                })
                
        # 2. 파일 목록 추출
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'] == prefix: continue # 폴더 자체(껍데기)는 제외
                
                file_name = obj['Key'].replace(prefix, '')
                # R2는 기본적으로 비공개이므로, 코드에서 1시간짜리 임시 열람(GET) 통행증을 발급해 줍니다.
                presigned_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': obj['Key']},
                    ExpiresIn=3600
                )
                
                is_img = file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.heic'))
                
                files_data.append({
                    "id": obj['Key'],
                    "name": file_name,
                    "mimeType": "image/*" if is_img else "application/octet-stream",
                    "webViewLink": presigned_url,
                    "thumbnailLink": presigned_url if is_img else None,
                    "modifiedTime": obj['LastModified'].strftime('%Y-%m-%d %H:%M')
                })
                
        return jsonify({"status": "success", "data": files_data})
    except Exception as e:
        print(f"R2 List Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================================================================
# [신규 통합] Vercel을 거치지 않는 '직통 업로드(Presigned URL)' 티켓 발급 API
# ==============================================================================
@app.route('/api/r2/presigned', methods=['POST'])
def get_presigned_url():
    file_name = request.json.get('file_name')
    file_type = request.json.get('file_type')
    prefix = request.json.get('prefix') # 'docs/' 또는 'album/폴더명/'
    
    # URL 인코딩 문제 방지를 위해 파일명 안전 처리
    safe_file_name = urllib.parse.unquote(file_name)
    object_key = f"{prefix}{safe_file_name}"
    bucket = os.environ.get('R2_BUCKET_NAME')
    
    try:
        s3 = get_r2_client()
        # 프론트엔드에서 직접 R2로 쏠 수 있도록 1시간짜리 '업로드 전용(PUT) 통행증'을 발급
        presigned_url = s3.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': bucket,
                'Key': object_key,
                'ContentType': file_type
            },
            ExpiresIn=3600
        )
        return jsonify({"status": "success", "url": presigned_url, "key": object_key})
    except Exception as e:
        print(f"R2 Presigned Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 만능 데이터 호출 API (조회/생성)
@app.route('/api/<table>', methods=['GET', 'POST'])
def handle_table(table):
    if request.method == 'GET':
        query = "?order=created_at.desc"
        if table == 'tasks': query = "?order=start_date.desc"
        if table == 'events': query = "?order=event_date.desc"
        if table == 'event_comments': query = "?order=created_at.asc"
        
        data = db_request(table, 'GET', query)
        
        # [신규 추가] 이벤트 테이블 조회 시, 해당 이벤트의 앨범 폴더에서 사진 URL을 가져와 덧붙여줍니다.
        if table == 'events' and data:
            try:
                s3 = get_r2_client()
                bucket = os.environ.get('R2_BUCKET_NAME')
                
                for event in data:
                    event_title = event.get('title', '')
                    if not event_title:
                        event['imageUrls'] = []
                        continue
                        
                    prefix = f"album/{event_title}/"
                    image_urls = []
                    
                    try:
                        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
                        if 'Contents' in response:
                            for obj in response['Contents']:
                                if obj['Key'] == prefix: continue # 껍데기 폴더 제외
                                
                                # 프론트엔드에서 썸네일을 볼 수 있도록 1시간짜리 Presigned URL 발급
                                presigned_url = s3.generate_presigned_url(
                                    'get_object',
                                    Params={'Bucket': bucket, 'Key': obj['Key']},
                                    ExpiresIn=3600
                                )
                                image_urls.append(presigned_url)
                    except Exception as e:
                        print(f"R2 Image List Error for event '{event_title}': {e}")
                    
                    event['imageUrls'] = image_urls
            except Exception as e:
                print(f"R2 Client Error during events fetch: {e}")

        return jsonify({"status": "success", "data": data})
        
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
