import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import sqlite3
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
from API_function import PixellotAPI

#맥에서 수정이야 이건 브런치야

# 페이지 설정 #
st.set_page_config(
    page_title="스케줄 예약 시스템",
    page_icon="📅",
    layout="wide"
)

# 데이터베이스 초기화
def init_scheduler_db():
    conn = sqlite3.connect('schedule_reservations.db')
    c = conn.cursor()
    
    # 스케줄 예약 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_name TEXT NOT NULL,
            selected_days TEXT NOT NULL,
            schedule_start_date TEXT NOT NULL,
            schedule_end_date TEXT NOT NULL,
            reservation_start_time TEXT NOT NULL,
            reservation_end_time TEXT NOT NULL,
            duration_minutes INTEGER,
            reservation_ids TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 예약 테이블 (스케줄에서 생성된 실제 예약)
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_date TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_scheduler_db()

# 스케줄러 초기화
scheduler = BackgroundScheduler()
scheduler.start()

# 프로그램 종료 시 스케줄러 종료
atexit.register(lambda: scheduler.shutdown())

# 예약 저장 함수 (스케줄러용)
def save_reservation(start_date, start_time, end_date, end_time, duration_minutes):
    conn = sqlite3.connect('schedule_reservations.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO reservations 
        (start_date, start_time, end_date, end_time, duration_minutes)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        str(start_date),
        str(start_time),
        str(end_date),
        str(end_time),
        duration_minutes
    ))
    reservation_id = c.lastrowid
    conn.commit()
    conn.close()
    return reservation_id

# 스케줄 예약 저장
def save_scheduled_reservation(schedule_name, selected_days, schedule_start_date, schedule_end_date, 
                                reservation_start_time, reservation_end_time, duration_minutes):
    conn = sqlite3.connect('schedule_reservations.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO scheduled_reservations 
        (schedule_name, selected_days, schedule_start_date, schedule_end_date, 
         reservation_start_time, reservation_end_time, duration_minutes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        schedule_name,
        json.dumps(selected_days),
        str(schedule_start_date),
        str(schedule_end_date),
        str(reservation_start_time),
        str(reservation_end_time),
        duration_minutes
    ))
    schedule_id = c.lastrowid
    conn.commit()
    conn.close()
    return schedule_id

# 스케줄 예약 목록 조회
def get_scheduled_reservations():
    conn = sqlite3.connect('schedule_reservations.db')
    df = pd.read_sql_query("SELECT * FROM scheduled_reservations ORDER BY created_at DESC", conn)
    conn.close()
    return df

# 스케줄 예약 삭제 (스케줄만 삭제, 생성된 예약은 유지)
def delete_scheduled_reservation(schedule_id):
    conn = sqlite3.connect('schedule_reservations.db')
    c = conn.cursor()
    # 스케줄만 삭제하고 생성된 예약은 유지
    c.execute("DELETE FROM scheduled_reservations WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()

# 스케줄 예약 수정
def update_scheduled_reservation(schedule_id, schedule_name, selected_days, schedule_start_date, schedule_end_date,
                                 reservation_start_time, reservation_end_time, duration_minutes):
    conn = sqlite3.connect('schedule_reservations.db')
    c = conn.cursor()
    c.execute(
        '''
        UPDATE scheduled_reservations
        SET schedule_name = ?, selected_days = ?, schedule_start_date = ?, schedule_end_date = ?,
            reservation_start_time = ?, reservation_end_time = ?, duration_minutes = ?
        WHERE id = ?
        ''',
        (
            schedule_name,
            json.dumps(selected_days),
            str(schedule_start_date),
            str(schedule_end_date),
            str(reservation_start_time),
            str(reservation_end_time),
            duration_minutes,
            schedule_id
        )
    )
    conn.commit()
    conn.close()

# 개별 예약 조회
def get_reservations():
    conn = sqlite3.connect('schedule_reservations.db')
    df = pd.read_sql_query("SELECT * FROM reservations ORDER BY start_date DESC, start_time DESC", conn)
    conn.close()
    return df

# 개별 예약 수정
def update_reservation(reservation_id, start_date, start_time, end_date, end_time, duration_minutes):
    conn = sqlite3.connect('schedule_reservations.db')
    c = conn.cursor()
    c.execute('''
        UPDATE reservations 
        SET start_date = ?, start_time = ?, end_date = ?, end_time = ?, duration_minutes = ?
        WHERE id = ?
    ''', (str(start_date), str(start_time), str(end_date), str(end_time), duration_minutes, reservation_id))
    conn.commit()
    conn.close()

# 개별 예약 삭제
def delete_reservation(reservation_id):
    conn = sqlite3.connect('schedule_reservations.db')
    c = conn.cursor()
    c.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    conn.commit()
    conn.close()

# 스케줄 활성화/비활성화
def toggle_schedule_active(schedule_id, is_active):
    conn = sqlite3.connect('schedule_reservations.db')
    c = conn.cursor()
    c.execute("UPDATE scheduled_reservations SET is_active = ? WHERE id = ?", (is_active, schedule_id))
    conn.commit()
    conn.close()

# 매일 자정 실행되는 스케줄러 작업
def daily_scheduler_job():
    """매일 00:00에 실행되어 활성 스케줄을 확인하고 예약 생성"""
    print(f"\n{'='*60}")
    print(f"📅 일일 스케줄러 실행: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    conn = sqlite3.connect('schedule_reservations.db')
    schedules_df = pd.read_sql_query(
        "SELECT * FROM scheduled_reservations WHERE is_active = 1", 
        conn
    )
    conn.close()
    
    today = datetime.now().date()
    today_weekday = today.weekday()  # 0=월요일, 6=일요일
    
    day_map = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
    
    for _, schedule in schedules_df.iterrows():
        schedule_start = datetime.strptime(schedule['schedule_start_date'], '%Y-%m-%d').date()
        schedule_end = datetime.strptime(schedule['schedule_end_date'], '%Y-%m-%d').date()
        
        # 오늘이 스케줄 기간 내인지 확인
        if schedule_start <= today <= schedule_end:
            selected_days = json.loads(schedule['selected_days'])
            selected_weekdays = [day_map[day] for day in selected_days if day in day_map]
            
            # 오늘이 선택된 요일인지 확인
            if today_weekday in selected_weekdays:
                # 예약 생성
                res_start_time = datetime.strptime(schedule['reservation_start_time'], '%H:%M:%S').time()
                res_end_time = datetime.strptime(schedule['reservation_end_time'], '%H:%M:%S').time()
                
                # 자정을 넘어가는 경우 처리
                if res_end_time < res_start_time:
                    end_date = today + timedelta(days=1)
                else:
                    end_date = today
                
                reservation_id = save_reservation(
                    start_date=today,
                    start_time=res_start_time,
                    end_date=end_date,
                    end_time=res_end_time,
                    duration_minutes=schedule['duration_minutes']
                )
                
                # scheduled_reservations에 reservation_id 추가
                conn = sqlite3.connect('schedule_reservations.db')
                c = conn.cursor()
                
                # 기존 reservation_ids 가져오기
                c.execute("SELECT reservation_ids FROM scheduled_reservations WHERE id = ?", (schedule['id'],))
                result = c.fetchone()
                
                if result and result[0]:
                    existing_ids = json.loads(result[0])
                else:
                    existing_ids = []
                
                existing_ids.append(reservation_id)
                
                # 업데이트
                c.execute(
                    "UPDATE scheduled_reservations SET reservation_ids = ? WHERE id = ?",
                    (json.dumps(existing_ids), schedule['id'])
                )
                conn.commit()
                conn.close()
                
                print(f"✅ 예약 생성: 스케줄 '{schedule['schedule_name']}' (ID: {schedule['id']})")
                print(f"   -> 예약 ID: {reservation_id}, 날짜: {today}, 시간: {res_start_time} ~ {res_end_time}\n")

# 스케줄러에 매일 자정 실행 작업 추가
if not scheduler.get_jobs():
    scheduler.add_job(
        daily_scheduler_job,
        CronTrigger(hour=0, minute=0),
        id='daily_reservation_scheduler',
        replace_existing=True
    )
    # 초기 등록 시에만 로그 출력 (페이지 로드마다 출력되지 않도록)
    # print("✅ 스케줄러 등록 완료: 매일 00:00 실행")

# 타이틀
st.title("📅 스케줄 기반 예약 시스템")
st.markdown("---")

# 세션 상태 초기화
if 'editing_reservation_id' not in st.session_state:
    st.session_state.editing_reservation_id = None
if 'editing_schedule_id' not in st.session_state:
    st.session_state.editing_schedule_id = None

st.info("""
**🤖 스케줄 예약 시스템**
- 매일 자정(00:00)에 자동으로 실행됩니다
- 활성화된 스케줄의 조건을 확인하여 자동으로 일반예약을 생성합니다
- 스케줄을 생성하면 지정된 기간 동안 선택한 요일에만 예약이 자동 생성됩니다
- 스케줄 삭제 시 이미 생성된 예약은 유지됩니다
""")

st.markdown("---")

# 스케줄 예약 생성 섹션
st.header("📝 스케줄 예약 생성")

# 초기값 설정 (session_state에 없으면)
current_time = datetime.now().time()
if 'res_start_time' not in st.session_state:
    st.session_state.res_start_time = current_time
if 'res_end_time' not in st.session_state:
    current_datetime = datetime.combine(datetime.now().date(), current_time)
    end_datetime = current_datetime + timedelta(hours=3)
    st.session_state.res_end_time = end_datetime.time()

# 프로토타입: 시간 입력은 폼 내부에서 직접 설정 (자동 +3시간 없이 수동 조정)

with st.form("schedule_form"):
    # 요일 선택
    st.markdown("**📅 반복 요일 선택**")
    days_of_week = ["월", "화", "수", "목", "금", "토", "일"]
    cols_days = st.columns(7)
    selected_days = []
    for idx, day in enumerate(days_of_week):
        with cols_days[idx]:
            if st.checkbox(day, key=f"schedule_day_{day}"):
                selected_days.append(day)
    
    # 스케줄 기간
    st.markdown("**📆 스케줄 기간**")
    min_date = datetime.now().date()
    max_date = min_date + timedelta(days=365)
    col_sch1, col_sch_sep, col_sch2 = st.columns([1, 0.2, 1])
    
    with col_sch1:
        schedule_start_date = st.date_input(
            "시작 날짜",
            min_value=min_date,
            max_value=max_date,
            value=min_date,
            key="schedule_start_date",
            label_visibility="collapsed"
        )
    
    with col_sch_sep:
        st.markdown("<h4 style='text-align: center; padding-top: 8px;'>~</h4>", unsafe_allow_html=True)
    
    with col_sch2:
        schedule_end_date = st.date_input(
            "종료 날짜",
            min_value=schedule_start_date,
            max_value=max_date,
            value=schedule_start_date + timedelta(days=30),
            key="schedule_end_date",
            label_visibility="collapsed"
        )

    # 예약 시간 설정 (폼 내부 입력)
    st.markdown("**⏰ 예약 시간 설정**")
    col_time1, col_time_sep, col_time2 = st.columns([1, 0.2, 1])
    
    with col_time1:
        reservation_start_time = st.time_input(
            "시작 시간",
            value=st.session_state.res_start_time,
            key="res_start_time",
            step=60,
            label_visibility="collapsed"
        )
    
    with col_time_sep:
        st.markdown("<h4 style='text-align: center; padding-top: 8px;'>~</h4>", unsafe_allow_html=True)
    
    with col_time2:
        reservation_end_time = st.time_input(
            "종료 시간",
            value=st.session_state.res_end_time,
            key="res_end_time",
            step=60,
            label_visibility="collapsed"
        )

    # 시간 계산
    temp_start = datetime.combine(datetime.now().date(), reservation_start_time)
    temp_end = datetime.combine(datetime.now().date(), reservation_end_time)
    if reservation_end_time < reservation_start_time:
        temp_end = datetime.combine(datetime.now().date() + timedelta(days=1), reservation_end_time)
    
    duration = temp_end - temp_start
    total_minutes = int(duration.total_seconds() / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    submitted = st.form_submit_button("✅ 스케줄 예약 생성", use_container_width=True, type="primary")
    
    if submitted:
        if not selected_days:
            st.error("⚠️ 반복 요일을 하나 이상 선택해주세요.")
        elif total_minutes <= 0:
            st.error("⚠️ 종료 시간이 시작 시간보다 늦어야 합니다.")
        else:
            # 스케줄 이름 자동 생성
            schedule_name = f"{', '.join(selected_days)} {reservation_start_time.strftime('%H:%M')}-{reservation_end_time.strftime('%H:%M')}"
            
            schedule_id = save_scheduled_reservation(
                schedule_name=schedule_name,
                selected_days=selected_days,
                schedule_start_date=schedule_start_date,
                schedule_end_date=schedule_end_date,
                reservation_start_time=reservation_start_time,
                reservation_end_time=reservation_end_time,
                duration_minutes=total_minutes
            )
            
            st.success(f"✨ 스케줄 예약이 생성되었습니다! (ID: {schedule_id})")
            st.info(f"⏱️ 1회 촬영 시간: {hours}시간 {minutes}분")
            st.balloons()
            st.rerun()

st.markdown("---")

# 스케줄 목록
st.header("📋 스케줄 예약 목록")

schedules_df = get_scheduled_reservations()

if not schedules_df.empty:
    for idx, row in schedules_df.iterrows():
        col_info, col_toggle, col_delete = st.columns([5, 0.8, 0.8])
        
        with col_info:
            try:
                days_list = json.loads(row['selected_days'])
                days_str = ', '.join(days_list)
            except:
                days_str = "알 수 없음"
            
            # 시간 계산
            duration_mins = row['duration_minutes']
            hours = duration_mins // 60
            minutes = duration_mins % 60
            
            status_emoji = "🟢" if row['is_active'] == 1 else "🔴"
            status_text = "활성" if row['is_active'] == 1 else "비활성"
            
            st.info(f"""
            {status_emoji} **[{status_text}]** {row['schedule_name']} (ID: {row['id']})  
            🔄 **반복 요일:** {days_str}  
            📅 **스케줄 기간:** {row['schedule_start_date']} ~ {row['schedule_end_date']}  
            ⏰ **예약 시간:** {row['reservation_start_time']} ~ {row['reservation_end_time']}  
            ⏱️ **1회 시간:** {hours}시간 {minutes}분  
            📅 **등록:** {row['created_at']}
            """)
        
        with col_toggle:
            if row['is_active'] == 1:
                if st.button("⏸️ 중지", key=f"pause_{row['id']}", use_container_width=True):
                    toggle_schedule_active(row['id'], 0)
                    st.success("스케줄이 비활성화되었습니다.")
                    st.rerun()
            else:
                if st.button("▶️ 시작", key=f"start_{row['id']}", use_container_width=True):
                    toggle_schedule_active(row['id'], 1)
                    st.success("스케줄이 활성화되었습니다.")
                    st.rerun()
        
        with col_delete:
            if st.button("🗑️ 삭제", key=f"del_schedule_{row['id']}", use_container_width=True):
                @st.dialog("삭제 확인")
                def confirm_delete_schedule(schedule_id):
                    st.warning("⚠️ 이 스케줄을 삭제하시겠습니까? (이미 생성된 예약은 유지됩니다)")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ 확인", use_container_width=True, type="primary", key=f"conf_sched_yes_{schedule_id}"):
                            delete_scheduled_reservation(schedule_id)
                            st.success("스케줄이 삭제되었습니다.")
                            st.rerun()
                    with col2:
                        if st.button("❌ 취소", use_container_width=True, key=f"conf_sched_no_{schedule_id}"):
                            st.rerun()
                confirm_delete_schedule(row['id'])

            # 삭제 버튼 바로 아래에 수정 버튼 배치
            if st.button("✏️ 수정", key=f"edit_schedule_{row['id']}", use_container_width=True):
                st.session_state.editing_schedule_id = row['id']
                st.rerun()

        # 수정 폼
        if st.session_state.editing_schedule_id == row['id']:
            with st.expander("✏️ 스케줄 수정", expanded=True, key=f"schedule_edit_{row['id']}"):
                # 기존 값 파싱
                try:
                    edit_days = json.loads(row['selected_days'])
                except:
                    edit_days = []
                try:
                    edit_start_date = datetime.strptime(row['schedule_start_date'], '%Y-%m-%d').date()
                except:
                    edit_start_date = datetime.now().date()
                try:
                    edit_end_date = datetime.strptime(row['schedule_end_date'], '%Y-%m-%d').date()
                except:
                    edit_end_date = datetime.now().date()
                try:
                    edit_start_time = datetime.strptime(row['reservation_start_time'], '%H:%M:%S').time()
                except:
                    try:
                        edit_start_time = datetime.strptime(row['reservation_start_time'], '%H:%M').time()
                    except:
                        edit_start_time = datetime.now().time()
                try:
                    edit_end_time = datetime.strptime(row['reservation_end_time'], '%H:%M:%S').time()
                except:
                    try:
                        edit_end_time = datetime.strptime(row['reservation_end_time'], '%H:%M').time()
                    except:
                        edit_end_time = datetime.now().time()

                # 반복 요일 선택
                st.markdown("**📅 반복 요일**")
                days_of_week = ["월", "화", "수", "목", "금", "토", "일"]
                cols_edit_days = st.columns(7)
                new_days = []
                for i, day in enumerate(days_of_week):
                    with cols_edit_days[i]:
                        if st.checkbox(day, value=day in edit_days, key=f"edit_day_{row['id']}_{day}"):
                            new_days.append(day)

                # 스케줄 기간
                st.markdown("**📆 스케줄 기간**")
                col_ed1, col_ed_sep, col_ed2 = st.columns([1, 0.2, 1])
                with col_ed1:
                    new_start_date = st.date_input(
                        "시작 날짜",
                        value=edit_start_date,
                        key=f"edit_schedule_start_{row['id']}"
                    )
                with col_ed_sep:
                    st.markdown("<h4 style='text-align: center; padding-top: 8px;'>~</h4>", unsafe_allow_html=True)
                with col_ed2:
                    new_end_date = st.date_input(
                        "종료 날짜",
                        value=edit_end_date,
                        min_value=new_start_date,
                        key=f"edit_schedule_end_{row['id']}"
                    )

                # 예약 시간
                st.markdown("**⏰ 예약 시간**")
                col_et1, col_et_sep, col_et2 = st.columns([1, 0.2, 1])
                with col_et1:
                    new_start_time = st.time_input(
                        "시작 시간",
                        value=edit_start_time,
                        key=f"edit_res_start_{row['id']}",
                        step=60
                    )
                with col_et_sep:
                    st.markdown("<h4 style='text-align: center; padding-top: 8px;'>~</h4>", unsafe_allow_html=True)
                with col_et2:
                    new_end_time = st.time_input(
                        "종료 시간",
                        value=edit_end_time,
                        key=f"edit_res_end_{row['id']}",
                        step=60
                    )

                # 시간 차이 계산
                temp_start = datetime.combine(datetime.now().date(), new_start_time)
                temp_end = datetime.combine(datetime.now().date(), new_end_time)
                if new_end_time < new_start_time:
                    temp_end = datetime.combine(datetime.now().date() + timedelta(days=1), new_end_time)
                duration = temp_end - temp_start
                duration_minutes = int(duration.total_seconds() / 60)

                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("💾 저장", key=f"save_schedule_{row['id']}", use_container_width=True, type="primary"):
                        if not new_days:
                            st.error("⚠️ 반복 요일을 하나 이상 선택해주세요.")
                        elif duration_minutes <= 0:
                            st.error("⚠️ 종료 시간이 시작 시간보다 늦어야 합니다.")
                        else:
                            schedule_name = f"{', '.join(new_days)} {new_start_time.strftime('%H:%M')}-{new_end_time.strftime('%H:%M')}"
                            update_scheduled_reservation(
                                schedule_id=row['id'],
                                schedule_name=schedule_name,
                                selected_days=new_days,
                                schedule_start_date=new_start_date,
                                schedule_end_date=new_end_date,
                                reservation_start_time=new_start_time,
                                reservation_end_time=new_end_time,
                                duration_minutes=duration_minutes
                            )
                            st.session_state.editing_schedule_id = None
                            st.success("✅ 스케줄이 수정되었습니다.")
                            st.rerun()
                with col_cancel:
                    if st.button("❌ 취소", key=f"cancel_schedule_{row['id']}", use_container_width=True):
                        st.session_state.editing_schedule_id = None
                        st.rerun()
        
        st.markdown("---")
else:
    st.info("등록된 스케줄 예약이 없습니다.")

# 생성된 예약 목록
st.markdown("---")
st.header("📅 생성된 예약 목록")

reservations_df = get_reservations()

if not reservations_df.empty:
    st.info(f"총 **{len(reservations_df)}**건의 예약이 생성되었습니다.")
    
    # 예약 목록 표시
    for idx, res in reservations_df.iterrows():
        col_info, col_edit, col_delete = st.columns([5, 0.7, 0.7])
        
        with col_info:
            # 시간 계산
            duration_mins = res['duration_minutes']
            days = duration_mins // (24 * 60)
            remaining_mins = duration_mins % (24 * 60)
            hours = remaining_mins // 60
            minutes = remaining_mins % 60
            
            duration_str = ""
            if days > 0:
                duration_str += f"{days}일 "
            if hours > 0:
                duration_str += f"{hours}시간 "
            if minutes > 0:
                duration_str += f"{minutes}분"
            
            # 시작/종료 날짜 및 시간
            start_datetime = f"{res['start_date']} {res['start_time']}"
            end_datetime = f"{res['end_date']} {res['end_time']}"
            
            st.success(f"""
            **[자동생성]** ID: {res['id']}  
            🎬 **예약 시간:** {start_datetime} ~ {end_datetime}  
            ⏱️ **총 시간:** {duration_str.strip()}  
            📅 **생성:** {res['created_at']}
            """)
        
        with col_edit:
            if st.button("✏️ 수정", key=f"edit_res_{res['id']}", use_container_width=True):
                st.session_state.editing_reservation_id = res['id']
                st.rerun()
        
        with col_delete:
            if st.button("🗑️ 삭제", key=f"delete_res_{res['id']}", use_container_width=True):
                @st.dialog("삭제 확인")
                def confirm_delete_dialog(reservation_id):
                    st.warning("⚠️ 이 예약을 삭제하시겠습니까?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ 확인", use_container_width=True, type="primary", key=f"conf_res_yes_{reservation_id}"):
                            delete_reservation(reservation_id)
                            st.session_state.editing_reservation_id = None
                            st.rerun()
                    with col2:
                        if st.button("❌ 취소", use_container_width=True, key=f"conf_res_no_{reservation_id}"):
                            st.rerun()
                confirm_delete_dialog(res['id'])
        
        # 수정 모드
        if st.session_state.editing_reservation_id == res['id']:
            with st.expander("✏️ 예약 수정", expanded=True, key=f"reservation_edit_schedule_{res['id']}"):
                # 기존 값 파싱
                try:
                    edit_start_date = datetime.strptime(res['start_date'], '%Y-%m-%d').date()
                except:
                    edit_start_date = datetime.now().date()
                
                try:
                    edit_start_time = datetime.strptime(res['start_time'], '%H:%M:%S').time()
                except:
                    try:
                        edit_start_time = datetime.strptime(res['start_time'], '%H:%M').time()
                    except:
                        edit_start_time = datetime.now().time()
                
                try:
                    edit_end_date = datetime.strptime(res['end_date'], '%Y-%m-%d').date()
                except:
                    edit_end_date = datetime.now().date()
                
                try:
                    edit_end_time = datetime.strptime(res['end_time'], '%H:%M:%S').time()
                except:
                    try:
                        edit_end_time = datetime.strptime(res['end_time'], '%H:%M').time()
                    except:
                        edit_end_time = datetime.now().time()
                
                col_date1, col_time1, col_date2, col_time2 = st.columns(4)
                
                with col_date1:
                    new_start_date = st.date_input("시작 날짜", value=edit_start_date, key=f"edit_start_date_{res['id']}")
                
                with col_time1:
                    new_start_time = st.time_input("시작 시간", value=edit_start_time, key=f"edit_start_time_{res['id']}")
                
                with col_date2:
                    new_end_date = st.date_input("종료 날짜", value=edit_end_date, key=f"edit_end_date_{res['id']}")
                
                with col_time2:
                    new_end_time = st.time_input("종료 시간", value=edit_end_time, key=f"edit_end_time_{res['id']}")
                
                col_save, col_cancel = st.columns(2)
                
                with col_save:
                    if st.button("💾 저장", key=f"save_edit_{res['id']}", use_container_width=True, type="primary"):
                        # 시간 계산
                        start_dt = datetime.combine(new_start_date, new_start_time)
                        end_dt = datetime.combine(new_end_date, new_end_time)
                        
                        if end_dt > start_dt:
                            duration = end_dt - start_dt
                            total_minutes = int(duration.total_seconds() / 60)
                            
                            update_reservation(
                                res['id'],
                                new_start_date,
                                new_start_time,
                                new_end_date,
                                new_end_time,
                                total_minutes
                            )
                            st.session_state.editing_reservation_id = None
                            st.success("✅ 예약이 수정되었습니다!")
                            st.rerun()
                        else:
                            st.error("⚠️ 종료 일시가 시작 일시보다 이전입니다.")
                
                with col_cancel:
                    if st.button("❌ 취소", key=f"cancel_edit_{res['id']}", use_container_width=True):
                        st.session_state.editing_reservation_id = None
                        st.rerun()
        
        st.markdown("---")
else:
    st.info("생성된 예약이 없습니다.")

# 테스트 버튼 (개발용)
st.markdown("---")
st.header("🧪 테스트")

col_test1, col_test2 = st.columns(2)

with col_test1:
    if st.button("🚀 스케줄러 즉시 실행 (테스트)", help="자정을 기다리지 않고 즉시 스케줄러를 실행합니다", use_container_width=True):
        daily_scheduler_job()
        st.success("✅ 스케줄러가 실행되었습니다! 터미널에서 로그를 확인하세요.")
        st.rerun()

with col_test2:
    if st.button("📊 데이터베이스 조회", help="전체 데이터베이스 내용을 터미널에 출력합니다", use_container_width=True):
        print("\n" + "="*80)
        print("📊 데이터베이스 전체 조회")
        print("="*80)
        
        conn = sqlite3.connect('schedule_reservations.db')
        
        # 스케줄 예약 테이블
        print("\n[scheduled_reservations 테이블]")
        df_scheduled = pd.read_sql_query("SELECT * FROM scheduled_reservations ORDER BY id", conn)
        if not df_scheduled.empty:
            print(df_scheduled.to_string(index=False))
        else:
            print("데이터 없음")
        
        # 예약 테이블
        print("\n[reservations 테이블]")
        df_reservations = pd.read_sql_query("SELECT * FROM reservations ORDER BY id DESC LIMIT 20", conn)
        if not df_reservations.empty:
            print(df_reservations.to_string(index=False))
        else:
            print("데이터 없음")
        
        conn.close()
        
        print("\n" + "="*80)
        print("✅ 데이터베이스 조회 완료")
        print("="*80 + "\n")
        
        st.success("✅ 데이터베이스 내용이 터미널에 출력되었습니다!")


# 푸터
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <small>스케줄 예약 시스템 v1.0 | Powered by APScheduler</small>
</div>
""", unsafe_allow_html=True)
