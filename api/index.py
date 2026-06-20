from flask import Flask, render_template, request, jsonify, send_from_directory
import urllib.request
import json
import os

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
