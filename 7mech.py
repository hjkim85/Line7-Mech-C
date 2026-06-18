import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController

# ==========================================
# 1. 페이지 및 DB 연결 설정
# ==========================================
st.set_page_config(page_title="Line7-Mech-C", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# ==========================================
# 🔒 2. 로그인 차단막 (보안 게이트) 및 쿠키 설정
# ==========================================
controller = CookieController()

# 쿠키에서 인증 기록 확인
is_authenticated = controller.get('c_team_auth')

# 인증 기록이 없으면 로그인 화면만 보여주고 아래 코드는 실행(stop) 중지
if is_authenticated != 'true':
    st.markdown("<h2 style='text-align: center; color: #1E3A8A; margin-top:50px;'>🔒 Line7-Mech-C 업무 포털</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b;'>C조 관계자 외 접근을 금지합니다.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            pwd_input = st.text_input("접속 비밀번호를 입력하십시오", type="password")
            submit_btn = st.form_submit_button("로그인", use_container_width=True)
            
            if submit_btn:
                # secrets.toml에 저장된 비밀번호와 비교
                if pwd_input == st.secrets.get("APP_PASSWORD", "7mech"):
                    # 비밀번호가 맞으면 쿠키에 VIP 입장권 발급 (1년 유지)
                    controller.set('c_team_auth', 'true', max_age=31536000)
                    st.success("인증되었습니다. 환영합니다!")
                    st.rerun()
                else:
                    st.error("❌ 비밀번호가 일치하지 않습니다.")
    
    # ⛔ 로그인이 안 되었으므로 여기서 앱 화면 그리기를 강제 종료함
    st.stop()


# ==========================================
# 3. 공통 함수 및 상태(State) 초기화 (로그인 된 사람만 이 아래를 볼 수 있음)
# ==========================================
if "cal_year" not in st.session_state:
    st.session_state.cal_year = datetime.today().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = datetime.today().month

def get_shift(target_date):
    base_date = date(2026, 6, 1)
    cycle = ['A/D', 'A/C', 'B/A', 'B/D', 'C/B', 'C/A', 'D/C', 'D/B']
    diff_days = (target_date - base_date).days
    shift_index = (diff_days + 3) % 8
    return cycle[shift_index]

def load_tasks(is_starred_only=False):
    query = supabase.table("tasks").select("*")
    if is_starred_only:
        query = query.eq("is_starred", True)
    return query.order("created_at", desc=True).execute().data

def toggle_star(task_id, current_status):
    supabase.table("tasks").update({"is_starred": not current_status}).eq("id", task_id).execute()

def load_notices():
    return supabase.table("notices").select("*").order("created_at", desc=True).execute().data

def load_events(status="활성"):
    return supabase.table("events").select("*").eq("status", status).order("created_at", desc=True).execute().data

def change_event_status(event_id, new_status):
    supabase.table("events").update({"status": new_status}).eq("id", event_id).execute()

def load_comments(event_id):
    return supabase.table("event_comments").select("*").eq("event_id", event_id).order("created_at", desc=False).execute().data

def add_comment(event_id, content):
    data = {"event_id": event_id, "content": content, "user_email": "c_team@incheon.go.kr"}
    supabase.table("event_comments").insert(data).execute()

def render_task_card(task, prefix=""):
    try:
        t_date = datetime.strptime(task['start_date'], "%Y-%m-%d").date()
    except:
        t_date = date.today()

    today = date.today()
    status = task.get('status', '활성')

    if status == '종료':
        title_style = "color: #94a3b8; text-decoration: line-through;" 
    elif t_date == today:
        title_style = "color: #8b0000; font-weight: bold;" 
    elif t_date < today:
        title_style = "color: #0284c7;" 
    else:
        title_style = "color: #1e293b;" 

    with st.container(border=True):
        c1, c2 = st.columns([8, 2])
        with c1:
            left_star = "⭐" if task.get('is_starred') else ""
            st.markdown(f"<span style='{title_style}; font-size:1.05em;'>{left_star} [{task['category']}] {task['title']}</span>", unsafe_allow_html=True)
            st.caption(f"일정: {task['date_type']} ({task['start_date']}) | 상태: {status} | 내용: {task['content']}")
        
        with c2:
            star_label = "⭐ 해제" if task.get('is_starred') else "☆ 중요"
            if st.button(star_label, key=f"{prefix}star_{task['id']}"):
                toggle_star(task['id'], task.get('is_starred', False))
                st.rerun()

        with st.expander("🛠️ 관리 (수정/종료/삭제)"):
            edit_title = st.text_input("제목 수정", value=task['title'], key=f"{prefix}t_{task['id']}")
            cat_options = ["일반", "점검", "자체", "외주", "제출", "보고"]
            current_cat = task['category'] if task['category'] in cat_options else "일반"
            edit_cat = st.selectbox("분류 수정", cat_options, index=cat_options.index(current_cat), key=f"{prefix}c_{task['id']}")
            edit_content = st.text_area("내용 수정", value=task['content'], key=f"{prefix}cnt_{task['id']}")

            btn1, btn2, btn3 = st.columns(3)
            with btn1:
                if st.button("💾 내용 수정", key=f"{prefix}btn_edit_{task['id']}"):
                    supabase.table("tasks").update({"title": edit_title, "category": edit_cat, "content": edit_content}).eq("id", task['id']).execute()
                    st.rerun()
            with btn2:
                if status == '활성':
                    if st.button("✔️ 업무 종료", key=f"{prefix}btn_close_{task['id']}"):
                        supabase.table("tasks").update({"status": "종료", "is_starred": False}).eq("id", task['id']).execute()
                        st.rerun()
                else:
                    if st.button("🔄 활성 전환", key=f"{prefix}btn_reopen_{task['id']}"):
                        supabase.table("tasks").update({"status": "활성"}).eq("id", task['id']).execute()
                        st.rerun()
            with btn3:
                if st.button("🗑️ 영구 삭제", key=f"{prefix}btn_del_{task['id']}", type="primary"):
                    supabase.table("tasks").delete().eq("id", task['id']).execute()
                    st.rerun()

# ==========================================
# 4. 화면 UI 구성
# ==========================================
st.markdown("<h3 style='text-align: center; color: #1E3A8A;'>📱 Line7-Mech-C 업무 포털</h3>", unsafe_allow_html=True)
st.markdown("---")

tabs = st.tabs(["📢 중요알림", "📅 업무캘린더", "📋 업무목록", "🚨 이벤트(활성)", "✅ 이벤트(종결)", "📁 자료실", "🖼️ 앨범"])

with tabs[0]:
    st.markdown("<h5 style='color:#1e3a8a;'>📌 C조 자체 중요알림</h5>", unsafe_allow_html=True)
    with st.expander("➕ 새 중요알림 등록하기"):
        n_content = st.text_area("알림 내용을 입력하세요")
        if st.button("등록 완료"):
            if n_content:
                supabase.table("notices").insert({"content": n_content, "user_email": "c_team@incheon.go.kr"}).execute()
                st.rerun()

    notices = load_notices()
    if notices:
        for n in notices:
            with st.container(border=True):
                st.markdown(f"<div style='background-color:#eff6ff; padding:15px; border-radius:5px; border-left:5px solid #3b82f6; margin-bottom:10px;'><b>{n['content']}</b></div>", unsafe_allow_html=True)
                with st.expander("알림 관리"):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        edit_n = st.text_input("알림 수정", value=n['content'], key=f"n_val_{n['id']}", label_visibility="collapsed")
                    with c2:
                        if st.button("수정", key=f"n_edit_{n['id']}"):
                            supabase.table("notices").update({"content": edit_n}).eq("id", n['id']).execute()
                            st.rerun()
                        if st.button("삭제", key=f"n_del_{n['id']}", type="primary"):
                            supabase.table("notices").delete().eq("id", n['id']).execute()
                            st.rerun()
    else:
        st.info("등록된 자체 중요알림이 없습니다.")

    st.markdown("---")
    st.markdown("<h5 style='color:#ea580c;'>⭐ 중요 표시된 현장 업무</h5>", unsafe_allow_html=True)
    starred_tasks = load_tasks(is_starred_only=True)
    if starred_tasks:
        for task in starred_tasks:
            render_task_card(task, prefix="t1_") 
    else:
        st.write("현재 중요(⭐) 표시된 업무가 없습니다.")

with tabs[1]:
    st.subheader("📅 이달의 업무 달력")
    col_l, col_m, col_r = st.columns([1, 4, 1])
    with col_l:
        if st.button("◀ 이전 달"):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with col_m:
        st.markdown(f"<h4 style='text-align:center; color:#1e293b; margin:0;'>{st.session_state.cal_year}년 {st.session_state.cal_month}월</h4>", unsafe_allow_html=True)
    with col_r:
        if st.button("다음 달 ▶", use_container_width=True):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()
            
    all_tasks = load_tasks()
    cyear = st.session_state.cal_year
    cmonth = st.session_state.cal_month
    
    tasks_by_date = {}
    if all_tasks:
        for t in all_tasks:
            if t.get('start_date'):
                tasks_by_date.setdefault(t['start_date'], []).append(t)

    calendar.setfirstweekday(calendar.SUNDAY)
    cal = calendar.monthcalendar(cyear, cmonth)
    today = datetime.today()
    
    html_cal = """
    <style>
        .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 15px; }
        .cal-th { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 8px; text-align: center; color: #475569; font-weight: bold; font-size: 0.9em; }
        .cal-td { border: 1px solid #e2e8f0; height: 110px; vertical-align: top; padding: 4px; }
        .cal-td-empty { background-color: #f1f5f9; border: 1px solid #e2e8f0; }
        .cal-day { font-weight: bold; color: #1e293b; margin-bottom: 4px; font-size: 0.9em; text-align: left; display: flex; justify-content: space-between; align-items: center;}
        .cal-task { font-size: 0.75em; background-color: #dbeafe; color: #1e40af; padding: 3px 5px; margin-bottom: 3px; border-radius: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border-left: 3px solid #3b82f6; }
        .cal-task.starred { background-color: #fef9c3; color: #9a3412; border-left: 3px solid #f59e0b; font-weight: bold; }
        .cal-task.closed { background-color: #f1f5f9; color: #94a3b8; border-left: 3px solid #cbd5e1; text-decoration: line-through; }
    </style>
    <table class='cal-table'>
        <tr>
            <th class='cal-th' style='color:#ef4444;'>일</th><th class='cal-th'>월</th><th class='cal-th'>화</th>
            <th class='cal-th'>수</th><th class='cal-th'>목</th><th class='cal-th'>금</th><th class='cal-th' style='color:#3b82f6;'>토</th>
        </tr>
    """
    
    for week in cal:
        html_cal += "<tr>"
        for day in week:
            if day == 0:
                html_cal += "<td class='cal-td-empty'></td>"
            else:
                date_str = f"{cyear}-{cmonth:02d}-{day:02d}"
                day_tasks = tasks_by_date.get(date_str, [])
                
                current_date_obj = date(cyear, cmonth, day)
                shift = get_shift(current_date_obj)
                shift_style = "color:#ef4444; font-weight:bold;" if "C" in shift else "color:#94a3b8; font-weight:normal;"
                shift_html = f"<span style='font-size:0.8em; {shift_style}'>{shift}</span>"
                
                tasks_html = ""
                for t in day_tasks:
                    star = "⭐" if t.get('is_starred') else ""
                    if t.get('status') == '종료':
                        css_class = "cal-task closed"
                    else:
                        css_class = "cal-task starred" if t.get('is_starred') else "cal-task"
                    tasks_html += f"<div class='{css_class}'>{star} {t['title']}</div>"
                
                day_style = "color: white; background-color: #3b82f6; padding: 2px 6px; border-radius: 50%;" if (day == today.day and cmonth == today.month and cyear == today.year) else ""
                
                html_cal += f"<td class='cal-td'><div class='cal-day'><span style='{day_style}'>{day}</span> {shift_html}</div>{tasks_html}</td>"
        html_cal += "</tr>"
    html_cal += "</table>"
    
    st.markdown(html_cal, unsafe_allow_html=True)

with tabs[2]:
    st.subheader("📋 전체 업무 목록")
    with st.expander("➕ 새 업무 카드 등록"):
        with st.form("task_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                t_title = st.text_input("업무 제목")
                t_cat = st.selectbox("분류", ["일반", "점검", "자체", "외주", "제출", "보고"])
            with col2:
                t_dtype = st.selectbox("날짜 분류", ["특정날짜", "기간", "기한"])
                t_date = st.date_input("날짜 (기한/시작일)")
            t_content = st.text_area("상세 업무 내용")
            if st.form_submit_button("업무 DB에 저장하기"):
                if t_title:
                    new_data = {
                        "title": t_title, "category": t_cat, "date_type": t_dtype,
                        "start_date": str(t_date), "content": t_content,
                        "user_email": "c_team@incheon.go.kr", "is_starred": False, "status": "활성"
                    }
                    supabase.table("tasks").insert(new_data).execute()
                    st.success("저장 완료!")
                    st.rerun()
                else:
                    st.warning("업무 제목을 입력해 주십시오.")

    tasks_data = load_tasks()
    if tasks_data:
        for task in tasks_data:
            render_task_card(task, prefix="t3_") 
    else:
        st.info("등록된 업무가 없습니다.")

with tabs[3]:
    st.subheader("🚨 진행 중인 이벤트 (고장/보수)")
    with st.expander("➕ 새 이벤트 등록"):
        with st.form("event_form", clear_on_submit=True):
            e_date = st.date_input("발생 일자")
            e_title = st.text_input("이벤트 제목")
            e_content = st.text_area("초기 증상 및 현상")
            if st.form_submit_button("이벤트 발생 등록"):
                if e_title:
                    e_data = {"event_date": str(e_date), "title": e_title, "content": e_content, "user_email": "c_team@incheon.go.kr"}
                    supabase.table("events").insert(e_data).execute()
                    st.success("등록 완료!")
                    st.rerun()

    active_events = load_events("활성")
    if active_events:
        for event in active_events:
            with st.expander(f"🔴 [{event['event_date']}] {event['title']}"):
                st.write(f"**초기 증상:** {event['content']}")
                st.markdown("---")
                comments = load_comments(event['id'])
                for c in comments:
                    date_str = c['created_at'].split('T')[0]
                    st.caption(f"💬 {date_str} - {c['content']}")
                col_c1, col_c2 = st.columns([4, 1])
                with col_c1:
                    new_comment = st.text_input("진행 상황/조치 내역 추가", key=f"c_input_{event['id']}")
                with col_c2:
                    if st.button("기록", key=f"c_btn_{event['id']}"):
                        if new_comment:
                            add_comment(event['id'], new_comment)
                            st.rerun()
                if st.button("✔️ 이 이벤트 종결하기", key=f"close_{event['id']}", type="primary"):
                    change_event_status(event['id'], "종결")
                    st.rerun()

with tabs[4]:
    st.subheader("✅ 종결된 이벤트 기록")
    closed_events = load_events("종결")
    if closed_events:
        for event in closed_events:
            with st.expander(f"🟢 [{event['event_date']}] {event['title']}"):
                st.write(f"**초기 증상:** {event['content']}")
                st.markdown("---")
                comments = load_comments(event['id'])
                for c in comments:
                    date_str = c['created_at'].split('T')[0]
                    st.caption(f"💬 {date_str} - {c['content']}")
                if st.button("활성 상태로 되돌리기", key=f"reopen_{event['id']}"):
                    change_event_status(event['id'], "활성")
                    st.rerun()

with tabs[5]:
    st.subheader("📁 자료실 (도면/매뉴얼)")
    st.info("💡 다음 단계에서 '구글 클라우드 API'를 연동할 예정입니다.")

with tabs[6]:
    st.subheader("🖼️ 현장 사진 앨범")
    st.info("💡 다음 단계에서 '구글 클라우드 API'를 연동할 예정입니다.")