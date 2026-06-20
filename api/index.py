from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    # 첫 화면으로 index.html을 송출합니다.
    return render_template('index.html')

if __name__ == '__main__':
    app.run()
