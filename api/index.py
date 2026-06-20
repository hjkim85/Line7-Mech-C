from flask import Flask, render_template, send_from_directory, jsonify
from supabase import create_client, Client
import os

app = Flask(__name__)

# 프로젝트 최상위 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 🌟 Vercel에 저장한 환경변수(수파베이스 주소 및 암호)를 안전하게 가져옵니다.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 수파베이스 클라이언트 초기화
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    # 메인 대문 화면을 보여줍니다.
    return render_template('index.html')

# 🌟 [업무 목록 및 캘린더 데이터 호출 API]
# 기존 7mech.py에서 스트림릿으로 그리던 데이터를 웹 화면(JavaScript)에 전달하는 창구입니다.
@app.route('/api/data')
def get_backend_data():
    try:
        # 데이터베이스의 테이블에서 전체 데이터를 가져옵니다.
        # 기존 테이블명에 맞춰 조회하며, 오류 방지를 위해 예외 처리를 강화했습니다.
        # (실제 테이블명이나 정렬 기준은 이후 UI 구성 시 정확히 맞출 예정입니다.)
        response = supabase.table("schedules").select("*").order("date", desc=False).execute()
        return jsonify({"status": "success", "data": response.data})
    except Exception as e:
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
