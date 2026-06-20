from flask import Flask, render_template, send_from_directory, jsonify, request
import urllib.request
import json
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 수파베이스 통신용 공통 암호 헤더 생성 함수
def get_headers(api_key):
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

@app.route('/')
def home():
    return render_template('index.html')

# 1. 데이터 불러오기 (Read)
@app.route('/api/data', methods=['GET'])
def get_data():
    try:
        url = f"{os.environ.get('SUPABASE_URL')}/rest/v1/events?select=*&order=event_date.asc"
        req = urllib.request.Request(url, headers=get_headers(os.environ.get("SUPABASE_KEY")))
        with urllib.request.urlopen(req) as res:
            return jsonify({"status": "success", "data": json.loads(res.read().decode('utf-8'))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 2. 새로운 일정 추가하기 (Create)
@app.route('/api/add', methods=['POST'])
def add_data():
    try:
        url = f"{os.environ.get('SUPABASE_URL')}/rest/v1/events"
        data = json.dumps(request.json).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=get_headers(os.environ.get("SUPABASE_KEY")), method='POST')
        with urllib.request.urlopen(req) as res:
            return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 3. 일정 삭제/종결하기 (Delete)
@app.route('/api/delete/<int:item_id>', methods=['DELETE'])
def delete_data(item_id):
    try:
        url = f"{os.environ.get('SUPABASE_URL')}/rest/v1/events?id=eq.{item_id}"
        req = urllib.request.Request(url, headers=get_headers(os.environ.get("SUPABASE_KEY")), method='DELETE')
        with urllib.request.urlopen(req) as res:
            return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/icon.png')
def serve_icon(): return send_from_directory(BASE_DIR, 'icon.png', mimetype='image/png')
@app.route('/manifest.json')
def serve_manifest(): return send_from_directory(BASE_DIR, 'manifest.json', mimetype='application/json')

if __name__ == '__main__':
    app.run()
