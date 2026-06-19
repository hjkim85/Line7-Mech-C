# ==============================================================================
# [Line7-Mech-C] 통합 업무 포털 시스템 설계도 및 메인 스크립트
# 기본 파일명: 7mech.py
# 
# 📋 [전체 단원 목차 (Table of Contents)]
#   [단원 1] 외부 라이브러리 로드 및 앱 기본 환경 설정
#   [단원 2] 사용자 보안 인증 시스템 (구글 OAuth / 로그인 회원 관리) - 향후 구현
#   [단원 3] 데이터베이스(Supabase) 클라이언트 초기화 및 연동 설정
#   [단원 4] 시스템 공통 비즈니스 로직 및 캘린더/교대근무 계산 함수
#   [단원 5] 수파베이스(Supabase) DB 통신 및 데이터 처리(CRUD) 함수
#   [단원 6] 모바일 최적화 고유 UI 컴포넌트 렌더링 함수
#   [단원 7] 글로벌 CSS 웹 스타일링 정의 (모바일 스크롤 및 컴포넌트 커스텀)
#   [단원 8] 메인 레이아웃 및 7대 핵심 기능 탭 구성
#   [단원 9] 개별 탭 세부 기능 구현 및 외부 클라우드 연동 인터페이스
# ==============================================================================

# ==============================================================================
# [단원 1] 외부 라이브러리 로드 및 앱 기본 환경 설정
# ==============================================================================
import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date
from supabase import create_client, Client

# 앱 상단 탭 제목 및 홈 화면 숏컷 아이콘(파비콘) 설정
st.set_page_config(page_title="Line7-Mech-C", page_icon="icon.png", layout="wide")


# ==============================================================================
# [단원 2] 사용자 보안 인증 시스템 (구글 OAuth / 로그인 회원 관리)
# ==============================================================================
# TODO: 다음 스텝에서 구글 로그인 연동 시 이 단원에 코드가 삽입됩니다.
# - 구글 계정 인증 여부 확인 로직
# - 로그인 완료 시 세션 상태(st.session_state)에 사용자 이름 및 이메일 저장
# - 미인증 유저 접속 시 화면 차단막 및 구글 로그인 버튼 활성화


# ==============================================================================
# [단원 3] 데이터베이스(Supabase) 클라이언트 초기화 및 연동 설정
# ==============================================================================
@st.cache_resource
def init_connection():
    """스트림릿 Secrets에 저장된 환경변수를 읽어 수파베이스 클라이언트를 초기화합니다."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()


# ==============================================================================
# [단원 4] 시스템 공통 비즈니스 로직 및 캘린더/교대근무 계산 함수
# ==============================================================================
if "cal_year" not in st.session_state:
    st.session_state.cal_year = datetime.today().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = datetime.today().month

def get_shift(target_date):
    """
    4조2교대 8일 주기 근무조를 영구 계산합니다.
    기준점: 2026년 6월 1일 = B/D 조
    """
    base_date = date(2026, 6, 1)
    cycle = ['A/D', 'A/C', 'B/A', 'B/D', 'C/B', 'C/A', 'D/C', 'D/B']
    diff_days = (target_date - base_date).days
    shift_index = (diff_days + 3) % 8
    return cycle[shift_index]


# ==============================================================================
# [단원 5] 수파베이스(Supabase) DB 통신 및 데이터 처리(CRUD) 함수
# ==============================================================================
def load_tasks(is_starred_only=False):
    """전체 현장 업무 일정을 불러옵니다."""
    try:
        query = supabase.table("tasks").select("*")
        if is_starred_only:
            query = query.eq("is_starred", True)
        return query.order("created_at", desc=True).execute().data
    except Exception as e:
        st.error(f"❌ 업무 목록 DB 연동 실패: {e}")
        return []

def toggle_star(task_id, current_status):
    """업무의 중요 표시(별표) 상태를 반전시킵니다."""
    try:
        supabase.table("tasks").update({"is_starred": not current_status}).eq("id", task_id).execute()
    except Exception as e:
        st.error(f"❌ 중요 표시 변경 실패: {e}")

def load_notices():
    """상단 공지용 자체 중요알림 목록을 불러옵니다."""
    try:
        return supabase.table("notices").select("*").order("created_at", desc=True).execute().data
    except Exception as e:
        st.error(f"❌ 중요알림 DB 연동 실패: {e}")
        return []

def load_events(status="활성"):
    """진행 중 또는 종결된 설비 고장/보수 이벤트 이력을 불러옵니다."""
    try:
        return supabase.table("events").select("*").eq("status", status).order("created_at", desc=True).execute().data
    except Exception as e:
        st.error(f"❌ 이벤트 DB 연동 실패: {e}")
        return []

def change_event_status(event_id, new_status):
    """이벤트의 상태를 활성 또는 종결로 변환합니다."""
    try:
        supabase.table("events").update({"status": new_status}).eq("id", event_id).execute()
    except Exception as e:
        st.error(f"❌ 이벤트 상태 변경 실패: {e}")

def load_comments(event_id):
    """특정 이벤트 하위의 조치 내역 댓글을 실시간 로드합니다."""
    try:
        return supabase.table("event_comments").select("*").eq("event_id", event_id).order("created_at", desc=False).execute().data
    except Exception as e:
        st.error(f"❌ 댓글 로드 실패: {e}")
        return []

def add_comment(event_id, content):
    """조치 내역 댓글을 등록합니다."""
    try:
        data = {"event_id": event_id, "content": content, "user_email": "c_team"}
        supabase.table("event_comments").insert(data).execute()
    except Exception as e:
        st.error(f"❌ 댓글 등록 실패: {e}")

def delete_comment(comment_id):
    """등록된 조치 내역 댓글을 삭제합니다."""
    try:
        supabase.table("event_comments").delete().eq("id", comment_id).execute()
    except Exception as e:
        st.error(f"❌ 댓글 삭제 실패: {e}")


# ==============================================================================
# [단원 6] 모바일 최적화 고유 UI 컴포넌트 렌더링 함수
# ==============================================================================
def render_task_card(task, prefix=""):
    """
    [중요알림] 및 [업무목록] 탭에서 공통 사용하는 초경량 모바일 최적화 카드입니다.
    날짜 상태별 색상 제어 및 수정/종료/삭제 통합 원터치 인터페이스를 제공합니다.
    """
    try:
        t_date = datetime.strptime(task['start_date'], "%Y-%m-%d").date()
    except:
        t_date = date.today()

    today = date.today()
    status = task.get('status', '활성')

    # 상태 및 날짜별 타이틀 스크립트 스타일링
    if status == '종료':
        title_style = "color: #94a3b8; text-decoration: line-through;" 
    elif t_date == today:
        title_style = "color: #8b0000; font-weight: bold;" 
    elif t_date < today:
        title_style = "color: #0284c7;" 
    else:
        title_style = "color: #1e293b;" 

    with st.container(border=True):
        st.markdown(f"<span style='{title_style}; font-size:1.05em;'>[{task['category']}] {task['title']}</span>", unsafe_allow_html=True)
        st.caption(f"일정: {task['date_type']} ({task['start_date']}) | 내용: {task['content']}")
        
        # 액션 제어 패널 (4열 압축)
        c1, c2, c3, c4 = st.columns(4)
        star_icon = "⭐" if task.get('is_starred') else "☆"
        
        if c1.button(star_icon, key=f"{prefix}s_{task['id']}", use_container_width=True, help="중요 표시"):
            toggle_star(task['id'], task.get('is_starred', False))
            st.rerun()
            
        if c2.button("✏️", key=f"{prefix}e_{task['id']}", use_container_width=True, help="수정"):
            st.session_state[f"edit_{prefix}_{task['id']}"] = not st.session_state.get(f"edit_{prefix}_{task['id']}", False)
            
        if status == '활성':
            if c3.button("✔️", key=f"{prefix}c_{task['id']}", use_container_width=True, help="종료"):
                supabase.table("tasks").update({"status": "종료", "is_starred": False}).eq("id", task['id']).execute()
                st.rerun()
        else:
            if c3.button("🔄", key=f"{prefix}o_{task['id']}", use_container_width=True, help="활성 전환"):
                supabase.table("tasks").update({"status": "활성"}).eq("id", task['id']).execute()
                st.rerun()
                
        if c4.button("🗑️", key=f"{prefix}d_{task['id']}", use_container_width=True, help="삭제"):
            st.session_state[f"del_{prefix}_{task['id']}"] = True

        # [하위 세부 로직 1] 인라인 업무 수정 폼
        if st.session_state.get(f"edit_{prefix}_{task['id']}"):
            st.markdown("---")
            edit_title = st.text_input("제목 수정", value=task['title'], key=f"{prefix}t_{task['id']}")
            cat_options = ["일반", "점검", "자체", "외주", "제출", "보고"]
            current_cat = task['category'] if task['category'] in cat_options else "일반"
            edit_cat = st.selectbox("분류 수정", cat_options, index=cat_options.index(current_cat), key=f"{prefix}c_{task['id']}")
            edit_content = st.text_area("내용 수정", value=task['content'], key=f"{prefix}cnt_{task['id']}")
            if st.button("💾 저장하기", key=f"{prefix}save_{task['id']}"):
                supabase.table("tasks").update({"title": edit_title, "category": edit_cat, "content": edit_content}).eq("id", task['id']).execute()
                st.session_state[f"edit_{prefix}_{task['id']}"] = False
                st.rerun()

        # [하위 세부 로직 2] 영구 삭제 2단계 안전 팝업창
        if st.session_state.get(f"del_{prefix}_{task['id']}"):
            st.warning("⚠️ 정말 이 업무를 영구 삭제하시겠습니까?")
            dc1, dc2 = st.columns(2)
            if dc1.button("네, 삭제합니다", key=f"{prefix}dy_{task['id']}", type="primary"):
                supabase.table("tasks").delete().eq("id", task['id']).execute()
                st.session_state[f"del_{prefix}_{task['id']}"] = False
                st.rerun()
            if dc2.button("취소", key=f"{prefix}dn_{task['id']}"):
                st.session_state[f"del_{prefix}_{task['id']}"] = False
                st.rerun()


# ==============================================================================
# [단원 7] 글로벌 CSS 웹 스타일링 정의 
# ==============================================================================
st.markdown("""
<style>
    /* 이벤트 종결 버튼 전용 소프트 그린 테마화 */
    button:has(div:contains("이 이벤트 종결하기")) {
        background-color: #22c55e !important;
        color: white !important;
        border: none !important;
    }
    
    /* 모바일 환경에서 컬럼들이 세로로 깨지는 것 강제 방지 (버튼 4열 한줄 고정) */
    @media (max-width: 576px) {
        [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
        }
        [data-testid="stHorizontalBlock"] > div {
            min-width: 0 !important;
            padding-left: 2px !important;
            padding-right: 2px !important;
        }
    }

    /* 캘린더 기본 레이아웃 CSS */
    .cal-wrapper { overflow-x: auto; width: 100%; padding-bottom: 10px; }
    .cal-table { min-width: 700px; width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 15px; }
    .cal-th { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 8px; text-align: center; color: #475569; font-weight: bold; font-size: 0.9em; }
    .cal-td { border: 1px solid #e2e8f0; height: 110px; vertical-align: top; padding: 4px; }
    .cal-td-empty { background-color: #f1f5f9; border: 1px solid #e2e8f0; }
    .cal-day { font-weight: bold; color: #1e293b; margin-bottom: 4px; font-size: 0.9em; text-align: left; display: flex; justify-content: space-between; align-items: center;}
    
    /* 캘린더 내부 카드 CSS */
    .cal-task { font-size: 0.75em; background-color: #dbeafe; color: #1e40af; padding: 3px 5px; margin-bottom: 3px; border-radius: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border-left: 3px solid #3b82f6; cursor: pointer; display: block; }
    .cal-task.starred { background-color: #fef9c3; color: #9a3412; border-left: 3px solid #f59e0b; font-weight: bold; }
    .cal-task.closed { background-color: #f1f5f9; color: #94a3b8; border-left: 3px solid #cbd5e1; text-decoration: line-through; }
    
    /* [새 기능] 캘린더 팝업(모달) CSS */
    .modal-toggle { display: none; }
    .modal-bg {
        display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0,0,0,0.6); z-index: 999999; align-items: center; justify-content: center;
    }
    .modal-toggle:checked + .modal-bg { display: flex; }
    .modal-content {
        background: white; padding: 25px; border-radius: 12px; width: 85%; max-width: 450px;
        position: relative; box-shadow: 0 10px 25px rgba(0,0,0,0.2); text-align: left;
    }
    .modal-close {
        position: absolute; top: 15px; right: 20px; font-size: 26px; font-weight: bold;
        color: #94a3b8; cursor: pointer; line-height: 1;
    }
    .modal-close:hover { color: #ef4444; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# [단원 8] 메인 레이아웃 및 7대 핵심 기능 탭 구성
# ==============================================================================
st.markdown("""
<h3 style='text-align: center; color: #1E3A8A; display: flex; align-items: center; justify-content: center;'>
    <img src="https://raw.githubusercontent.com/hjkim85/Line7-Mech-C/main/icon.png" width="35" style="margin-right: 10px; border-radius: 8px;"> 
    Line7-Mech-C 업무 포털
</h3>
""", unsafe_allow_html=True)

st.markdown("---")

# 상단 7개 네비게이션 메뉴 탭 마운트
tabs = st.tabs(["📢 중요알림", "📅 업무캘린더", "📋 업무목록", "🚨 이벤트", "✅ 종결이벤트", "📁 자료실", "🖼️ 앨범"])


# ==============================================================================
# [단원 9] 개별 탭 세부 기능 구현 및 외부 클라우드 연동 인터페이스
# ==============================================================================

# ------------------------------------------------------------------------------
# 탭 1: 중요알림 (자체 공지방 + 별표 마킹 연동 이원화 시스템)
# ------------------------------------------------------------------------------
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
                st.markdown(f"<div style='background-color:#eff6ff; padding:15px; border-radius:5px; border-left:5px solid #3b82f6; margin-bottom:5px;'><b>{n['content']}</b></div>", unsafe_allow_html=True)
                nc1, nc2 = st.columns([1, 1])
                if nc1.button("✏️ 수정", key=f"ne_{n['id']}", use_container_width=True):
                    st.session_state[f"n_edit_{n['id']}"] = not st.session_state.get(f"n_edit_{n['id']}", False)
                if nc2.button("🗑️ 삭제", key=f"nd_{n['id']}", use_container_width=True):
                    supabase.table("notices").delete().eq("id", n['id']).execute()
                    st.rerun()
                if st.session_state.get(f"n_edit_{n['id']}"):
                    edit_n = st.text_input("내용 수정", value=n['content'], key=f"n_val_{n['id']}")
                    if st.button("저장", key=f"n_save_{n['id']}"):
                        supabase.table("notices").update({"content": edit_n}).eq("id", n['id']).execute()
                        st.session_state[f"n_edit_{n['id']}"] = False
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

# ------------------------------------------------------------------------------
# 탭 2: 업무캘린더 (반응형 월 이동 & 8일 교대주기 관제형 달력)
# ------------------------------------------------------------------------------
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
    
    html_cal = "<div class='cal-wrapper'><table class='cal-table'>"
    html_cal += "<tr><th class='cal-th' style='color:#ef4444;'>일</th><th class='cal-th'>월</th><th class='cal-th'>화</th><th class='cal-th'>수</th><th class='cal-th'>목</th><th class='cal-th'>금</th><th class='cal-th' style='color:#3b82f6;'>토</th></tr>"
    
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
                    task_id = t['id']
                    star = "⭐" if t.get('is_starred') else ""
                    css_class = "cal-task closed" if t.get('status') == '종료' else ("cal-task starred" if t.get('is_starred') else "cal-task")
                    
                    safe_title = t['title'].replace("'", "&#39;").replace('"', "&quot;")
                    safe_content = t['content'].replace("'", "&#39;").replace('"', "&quot;").replace('\n', '<br>')
                    
                    tasks_html += f"""
                    <label for='modal_{task_id}' class='{css_class}'>{star} {safe_title}</label>
                    <input type='checkbox' id='modal_{task_id}' class='modal-toggle'>
                    <div class='modal-bg'>
                        <div class='modal-content'>
                            <label for='modal_{task_id}' class='modal-close'>&times;</label>
                            <h4 style='margin-top:0; color:#1e293b; font-size:1.1em;'>{star} [{t['category']}] {safe_title}</h4>
                            <p style='color:#64748b; font-size:0.85em; margin-bottom:10px;'>📌 일정: {t['date_type']} ({t['start_date']})<br>🚦 상태: {t.get('status', '활성')}</p>
                            <hr style='border:0; border-top:1px solid #e2e8f0; margin:10px 0;'>
                            <p style='color:#334155; font-size:0.95em; line-height:1.5;'>{safe_content}</p>
                        </div>
                    </div>
                    """
                
                day_style = "color: white; background-color: #3b82f6; padding: 2px 6px; border-radius: 50%;" if (day == today.day and cmonth == today.month and cyear == today.year) else ""
                html_cal += f"<td class='cal-td'><div class='cal-day'><span style='{day_style}'>{day}</span> {shift_html}</div>{tasks_html}</td>"
        html_cal += "</tr>"
    html_cal += "</table></div>"
    
    st.markdown(html_cal, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 탭 3: 업무목록 (전체 현장 업무 지시서 등록 및 열람 부서)
# ------------------------------------------------------------------------------
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
            if st.form_submit_button("일정 등록"):
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

# ------------------------------------------------------------------------------
# 탭 4: 이벤트 (설비 트러블슈팅 멀티라인 기록 연동룸)
# ------------------------------------------------------------------------------
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
                    cc1, cc2 = st.columns([9, 1])
                    cc1.caption(f"💬 {date_str} - {c['content']}")
                    if cc2.button("❌", key=f"del_c_{c['id']}"):
                        delete_comment(c['id'])
                        st.rerun()
                
                with st.form(key=f"c_form_{event['id']}", clear_on_submit=True):
                    new_comment = st.text_area("진행 상황/조치 내역 추가", key=f"c_input_{event['id']}", height=80)
                    if st.form_submit_button("기록"):
                        if new_comment:
                            add_comment(event['id'], new_comment)
                            st.rerun()
                            
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("이 이벤트 종결하기", key=f"close_{event['id']}"):
                    change_event_status(event['id'], "종결")
                    st.rerun()

# ------------------------------------------------------------------------------
# 탭 5: 종결이벤트 (영구 조치 내역 기술 백과사전 보관실)
# ------------------------------------------------------------------------------
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
                    cc1, cc2 = st.columns([9, 1])
                    cc1.caption(f"💬 {date_str} - {c['content']}")
                    if cc2.button("❌", key=f"del_c_{c['id']}"):
                        delete_comment(c['id'])
                        st.rerun()
                if st.button("활성 상태로 되돌리기", key=f"reopen_{event['id']}"):
                    change_event_status(event['id'], "활성")
                    st.rerun()

# ------------------------------------------------------------------------------
# 탭 6: 자료실 (도면/매뉴얼 - 구글 드라이브 연동 대기)
# ------------------------------------------------------------------------------
with tabs[5]:
    st.subheader("📁 자료실 (도면/매뉴얼)")
    st.info("💡 다음 단계에서 '구글 클라우드 및 구글 로그인'을 연동할 예정입니다.")

# ------------------------------------------------------------------------------
# 탭 7: 앨범 (현장 사진 - 구글 클라우드 스토리지 연동 대기)
# ------------------------------------------------------------------------------
with tabs[6]:
    st.subheader("🖼️ 현장 사진 앨범")
    st.info("💡 다음 단계에서 '구글 클라우드 및 구글 로그인'을 연동할 예정입니다.")