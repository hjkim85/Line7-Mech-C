from flask import Flask, render_template, send_from_directory
import os

app = Flask(__name__)

# 현재 파일이 있는 곳을 기준으로 최상위(루트) 폴더 위치를 찾습니다.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@app.route('/')
def home():
    return render_template('index.html')

# 브라우저가 아이콘을 요청하면 파일을 직접 찾아서 쏴줍니다.
@app.route('/icon.png')
def serve_icon():
    return send_from_directory(BASE_DIR, 'icon.png', mimetype='image/png')

# 스마트폰이 앱 설치 설계도를 요청하면 파일을 쏴줍니다.
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(BASE_DIR, 'manifest.json', mimetype='application/json')

if __name__ == '__main__':
    app.run()
