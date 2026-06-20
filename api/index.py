from flask import Flask, render_template, send_from_directory, jsonify
from supabase import create_client, Client
import os

app = Flask(__name__)

# 프로젝트 최상위 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 🌟 DB 클라이언트를 미리 연결하지 않고 비워둡니다.
supabase_client = None

# DB가 필요할 때만 조심스럽게 연결하는 안전 함수
def get_supabase():
    global supabase_client
    if supabase_client is None:
        SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
        
        # 키가 제대로 안 들어왔을 때를 대비한 에러 처리
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("Vercel 환경변수(비밀키)를 찾을 수 없습니다!")
            
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase_client

@app.route('/')
def home():
    # 🌟 DB 연결과 상관없이 일단 대문 화면부터 무조건 띄웁니다!
    return render_template('index.html')

@app.route('/api/data')
def get_backend_data():
    try:
        # 이 주소로 들어올 때만 안전하게 DB를 연결합니다.
        client = get_supabase()
        response = client.table("schedules").select("*").order("date", desc=False).execute()
        return jsonify({"status": "success", "data": response.data})
    except Exception as e:
        # 에러가 나도 앱이 뻗지 않고, 화면에 에러 이유를 친절하게 글자로 보여줍니다.
        return jsonify({"status": "error", "message": str(e)}), 500

# 🖼️ PC/모바일 아이콘 및 앱 설계도 전달 라우터
@app.route('/icon.png')
def serve_icon():
    return send_from_directory(BASE_DIR, 'icon.png', mimetype='image/png')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(BASE_DIR, 'manifest.json', mimetype='application/json')

if __name__ == '__main__':
    app.run()
