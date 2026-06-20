from flask import Flask, render_template, send_from_directory, jsonify
import urllib.request
import json
import os

app = Flask(__name__)

# 프로젝트 최상위 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@app.route('/')
def home():
    # 대문 화면 출력
    return render_template('index.html')

@app.route('/api/data')
def get_backend_data():
    try:
        # Vercel 환경변수 불러오기
        SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
        
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("Vercel 환경변수(비밀키)를 찾을 수 없습니다.")

        # 🌟 수파베이스 라이브러리를 쓰지 않고, 파이썬 순정 기능으로 웹 주소에 직접 요청합니다.
        # (만약 수파베이스에 만드신 테이블 이름이 schedules가 아니라면 그 이름으로 바꿔주세요)
        url = f"{SUPABASE_URL}/rest/v1/events?select=*"
        
        # 비밀키를 명찰처럼 달고 요청을 보냅니다.
        req = urllib.request.Request(url)
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        req.add_header("Content-Type", "application/json")
        
        # 직통 연결 후 데이터 수신
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return jsonify({"status": "success", "data": result})
            
    except urllib.error.HTTPError as e:
        # 테이블 이름이 틀렸거나 권한이 없을 때 뜨는 에러 처리
        error_msg = e.read().decode('utf-8')
        return jsonify({"status": "error", "message": f"DB 통신 거절됨: {error_msg}"}), 500
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
