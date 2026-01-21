import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import sqlite3
import json

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    
    # 반복예약 그룹 테이블 (테이블이 없을 때만 생성)
    c.execute('''
        CREATE TABLE IF NOT EXISTS repeat_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            selected_days TEXT NOT NULL,
            repeat_start_date TEXT NOT NULL,
            repeat_end_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER,
            total_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 개별 예약 테이블 (테이블이 없을 때만 생성)
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reservation_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_date TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER,
            repeat_group_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repeat_group_id) REFERENCES repeat_groups(id)
        )
    ''')
    conn.commit()
    conn.close()

# 일반 예약 저장
def save_reservation(start_date, start_time, end_date, end_time, duration_minutes):
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO reservations 
        (reservation_type, start_date, start_time, end_date, end_time, duration_minutes, repeat_group_id)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
    ''', (
        "일반예약",
        str(start_date),
        str(start_time),
        str(end_date),
        str(end_time),
        duration_minutes
    ))
    conn.commit()
    conn.close()

# 예약 목록 조회 (일반예약만)
def get_reservations():
    conn = sqlite3.connect('reservations.db')
    df = pd.read_sql_query(
        "SELECT * FROM reservations WHERE repeat_group_id IS NULL ORDER BY created_at DESC", 
        conn
    )
    conn.close()
    return df

# 반복예약 그룹 목록 조회
def get_repeat_groups():
    conn = sqlite3.connect('reservations.db')
    df = pd.read_sql_query("SELECT * FROM repeat_groups ORDER BY created_at DESC", conn)
    conn.close()
    return df

# 특정 반복예약 그룹의 개별 예약 조회
def get_reservations_by_group(group_id):
    conn = sqlite3.connect('reservations.db')
    df = pd.read_sql_query(
        "SELECT * FROM reservations WHERE repeat_group_id = ? ORDER BY start_date, start_time", 
        conn,
        params=(group_id,)
    )
    conn.close()
    return df

# 예약 수정 (일반예약)
def update_reservation(reservation_id, start_date, start_time, end_date, end_time, duration_minutes):
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    c.execute('''
        UPDATE reservations 
        SET start_date = ?, start_time = ?, end_date = ?, end_time = ?, duration_minutes = ?
        WHERE id = ?
    ''', (
        str(start_date),
        str(start_time),
        str(end_date),
        str(end_time),
        duration_minutes,
        reservation_id
    ))
    conn.commit()
    conn.close()

# 예약 삭제 (일반예약)
def delete_reservation(reservation_id):
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    c.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    conn.commit()
    conn.close()

# 개별 예약 삭제 (반복예약 그룹 내)
def delete_individual_reservation(reservation_id, group_id):
    """개별 예약 삭제 후 그룹의 total_count 업데이트"""
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    
    # 개별 예약 삭제
    c.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    
    # 그룹의 남은 개별 예약 개수 확인
    c.execute("SELECT COUNT(*) FROM reservations WHERE repeat_group_id = ?", (group_id,))
    remaining_count = c.fetchone()[0]
    
    if remaining_count > 0:
        # 그룹의 total_count 업데이트
        c.execute("UPDATE repeat_groups SET total_count = ? WHERE id = ?", (remaining_count, group_id))
    else:
        # 모든 개별 예약이 삭제되면 그룹도 삭제
        c.execute("DELETE FROM repeat_groups WHERE id = ?", (group_id,))
    
    conn.commit()
    conn.close()
    return remaining_count

# 반복예약 그룹 수정 (그룹과 관련된 모든 개별 예약의 시간도 수정)
def update_repeat_group(group_id, start_time, end_time, duration_minutes):
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    
    # 그룹 정보 업데이트
    c.execute('''
        UPDATE repeat_groups 
        SET start_time = ?, end_time = ?, duration_minutes = ?
        WHERE id = ?
    ''', (str(start_time), str(end_time), duration_minutes, group_id))
    
    # 관련된 모든 개별 예약의 시간도 업데이트
    c.execute('''
        UPDATE reservations 
        SET start_time = ?, end_time = ?, duration_minutes = ?
        WHERE repeat_group_id = ?
    ''', (str(start_time), str(end_time), duration_minutes, group_id))
    
    conn.commit()
    conn.close()

# 반복예약 그룹 삭제 (그룹과 관련된 모든 개별 예약도 삭제)
def delete_repeat_group(group_id):
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    # 관련된 모든 개별 예약 삭제
    c.execute("DELETE FROM reservations WHERE repeat_group_id = ?", (group_id,))
    # 그룹 삭제
    c.execute("DELETE FROM repeat_groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()

# 현재 시간 가져오기 (1분 단위로 올림)
def get_current_time():
    now = datetime.now()
    # 1분 단위로 올림
    rounded_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    return rounded_time.time()

# 시작 시간에서 3시간 후 계산
def calculate_end_datetime(start_date, start_time, hours_to_add=3):
    start_dt = datetime.combine(start_date, start_time)
    end_dt = start_dt + timedelta(hours=hours_to_add)
    return end_dt.date(), end_dt.time()

# 반복 예약을 위한 날짜 목록 생성
def generate_repeat_dates(start_date, end_date, selected_days):
    """선택된 요일에 해당하는 모든 날짜를 생성"""
    day_map = {
        "월": 0, "화": 1, "수": 2, "목": 3, 
        "금": 4, "토": 5, "일": 6
    }
    
    # 선택된 요일을 숫자로 변환
    selected_weekdays = [day_map[day] for day in selected_days if day in day_map]
    
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() in selected_weekdays:
            dates.append(current)
        current += timedelta(days=1)
    
    return dates

# 반복 예약 그룹 저장
def save_repeat_group(selected_days, repeat_start_date, repeat_end_date, 
                      start_time, end_time, duration_minutes):
    """반복 예약 그룹을 생성하고 각 날짜별 개별 예약도 생성"""
    dates = generate_repeat_dates(repeat_start_date, repeat_end_date, selected_days)
    
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    
    # 반복예약 그룹 생성
    c.execute('''
        INSERT INTO repeat_groups 
        (selected_days, repeat_start_date, repeat_end_date, start_time, end_time, 
         duration_minutes, total_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        json.dumps(selected_days),
        str(repeat_start_date),
        str(repeat_end_date),
        str(start_time),
        str(end_time),
        duration_minutes,
        len(dates)
    ))
    
    group_id = c.lastrowid
    
    # 각 날짜별로 개별 예약 생성
    for date in dates:
        c.execute('''
            INSERT INTO reservations 
            (reservation_type, start_date, start_time, end_date, end_time, 
             duration_minutes, repeat_group_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            "매주반복",
            str(date),
            str(start_time),
            str(date),
            str(end_time),
            duration_minutes,
            group_id
        ))
    
    conn.commit()
    conn.close()
    return len(dates)

# 페이지 설정
st.set_page_config(
    page_title="촬영 예약 시스템",
    page_icon="🎬",
    layout="wide"
)

# 데이터베이스 초기화
init_db()

# 세션 상태 초기화
if 'start_date' not in st.session_state:
    st.session_state.start_date = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'end_date' not in st.session_state:
    st.session_state.end_date = None
if 'end_time' not in st.session_state:
    st.session_state.end_time = None
if 'reservation_type' not in st.session_state:
    st.session_state.reservation_type = "일반예약"
if 'selected_days' not in st.session_state:
    st.session_state.selected_days = []
if 'repeat_start_date' not in st.session_state:
    st.session_state.repeat_start_date = None
if 'repeat_end_date' not in st.session_state:
    st.session_state.repeat_end_date = None
if 'editing_reservation_id' not in st.session_state:
    st.session_state.editing_reservation_id = None
if 'editing_group_id' not in st.session_state:
    st.session_state.editing_group_id = None
if 'expanded_group_id' not in st.session_state:
    st.session_state.expanded_group_id = None
if 'selected_individual_reservations' not in st.session_state:
    st.session_state.selected_individual_reservations = {}

# 타이틀
st.title("🎬 촬영 예약 시스템")
st.markdown("---")

# 메인 컨텐츠
col1, col2 = st.columns([2, 1])

with col1:
    # 예약 유형 선택
    st.markdown("### 예약유형")
    
    # CSS로 왼쪽 정렬 적용
    st.markdown("""
    <style>
    /* 라디오 버튼 왼쪽 정렬 */
    div[data-testid="stRadio"] > div {
        justify-content: flex-start !important;
    }
    /* 체크박스 왼쪽 정렬 */
    div[data-testid="stCheckbox"] {
        justify-content: flex-start !important;
    }
    /* 날짜 입력 왼쪽 정렬 */
    div[data-testid="stDateInput"] > div {
        justify-content: flex-start !important;
    }
    /* 시간 입력 왼쪽 정렬 */
    div[data-testid="stTimeInput"] > div {
        justify-content: flex-start !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    reservation_type = st.radio(
        "예약 유형을 선택하세요",
        options=["일반예약", "매주반복"],
        horizontal=True,
        label_visibility="collapsed",
        key="reservation_type_radio"
    )
    st.session_state.reservation_type = reservation_type
    
    # 매주반복 선택 시 요일 및 기간 선택
    if reservation_type == "매주반복":
        st.markdown("### 반복 요일 선택")
        
        # 요일 선택 버튼
        days_of_week = ["월", "화", "수", "목", "금", "토", "일"]
        cols_days = st.columns(7)
        
        selected_days = []
        for idx, day in enumerate(days_of_week):
            with cols_days[idx]:
                if st.checkbox(day, key=f"day_{day}"):
                    selected_days.append(day)
        
        st.session_state.selected_days = selected_days
        
        # 반복 기간 선택
        st.markdown("### 반복 기간")
        min_date = datetime.now().date()
        max_date = min_date + timedelta(days=90)
        
        col_repeat1, col_repeat_sep, col_repeat2 = st.columns([1, 0.2, 1])
        
        with col_repeat1:
            repeat_start_date = st.date_input(
                "반복 시작 날짜",
                min_value=min_date,
                max_value=max_date,
                value=min_date,
                key="repeat_start_date_input",
                label_visibility="collapsed"
            )
            st.session_state.repeat_start_date = repeat_start_date
        
        with col_repeat_sep:
            st.markdown("<h4 style='text-align: left; padding-top: 8px;'>~</h4>", unsafe_allow_html=True)
        
        with col_repeat2:
            repeat_end_date = st.date_input(
                "반복 종료 날짜",
                min_value=repeat_start_date if repeat_start_date else min_date,
                max_value=max_date,
                value=repeat_start_date if repeat_start_date else min_date,
                key="repeat_end_date_input",
                label_visibility="collapsed"
            )
            st.session_state.repeat_end_date = repeat_end_date
    
    st.markdown("---")
    
    st.header("📅 촬영 일시 선택")
    
    # 날짜 선택 (오늘부터 90일 후까지)
    min_date = datetime.now().date()
    max_date = min_date + timedelta(days=90)
    
    # 현재 시간 기반 기본값
    current_time = get_current_time()
    
    # 매주반복 선택 여부
    is_repeat = (reservation_type == "매주반복")
    
    # 5개 컬럼으로 수평 배치 (동일한 너비로 설정)
    col1_1, col1_2, col_separator, col1_3, col1_4 = st.columns([4, 3, 0.6, 4, 3])
    
    with col1_1:
        st.markdown("**📅 시작 날짜**")
        if is_repeat:
            # 매주반복일 때는 비활성화
            st.text_input(
                "촬영 시작 날짜",
                value="0000-00-00",
                disabled=True,
                key="start_date_disabled",
                label_visibility="collapsed"
            )
            start_date = min_date  # 내부 계산용
        else:
            start_date = st.date_input(
                "촬영 시작 날짜",
                min_value=min_date,
                max_value=max_date,
                value=min_date,
                key="start_date_input",
                label_visibility="collapsed"
            )
        st.session_state.start_date = start_date
    
    with col1_2:
        st.markdown("**⏰ 시작 시간**")
        start_time = st.time_input(
            "촬영 시작 시간",
            value=current_time,
            key="start_time_input",
            label_visibility="collapsed",
            step=60  # 1분 단위
        )
        st.session_state.start_time = start_time
    
    # 시작 시간 + 3시간 계산
    default_end_date, default_end_time = calculate_end_datetime(start_date, start_time, 3)
    
    with col_separator:
        st.markdown("**&nbsp;**")  # 빈 공간
        st.markdown("<h3 style='text-align: left; padding-top: 8px;'>~</h3>", unsafe_allow_html=True)
    
    with col1_3:
        st.markdown("**📅 종료 날짜**")
        if is_repeat:
            # 매주반복일 때는 비활성화
            st.text_input(
                "촬영 종료 날짜",
                value="0000-00-00",
                disabled=True,
                key="end_date_disabled",
                label_visibility="collapsed"
            )
            end_date = default_end_date  # 내부 계산용
        else:
            # 시작 날짜 이후만 선택 가능
            end_date = st.date_input(
                "촬영 종료 날짜",
                min_value=start_date if start_date else min_date,
                max_value=max_date,
                value=default_end_date,
                key="end_date_input",
                label_visibility="collapsed"
            )
        st.session_state.end_date = end_date
    
    with col1_4:
        st.markdown("**⏰ 종료 시간**")
        end_time = st.time_input(
            "촬영 종료 시간",
            value=default_end_time,
            key="end_time_input",
            label_visibility="collapsed",
            step=60  # 1분 단위
        )
        st.session_state.end_time = end_time
    
    # 종료 시간 유효성 검사
    if start_date and start_time and end_date and end_time:
        start_datetime = datetime.combine(start_date, start_time)
        end_datetime = datetime.combine(end_date, end_time)
        
        if end_datetime <= start_datetime:
            st.warning("⚠️ 종료 일시가 시작 일시보다 늦어야 합니다.")
    
    # 촬영 시간 계산 및 표시
    if st.session_state.start_date and st.session_state.start_time and st.session_state.end_date and st.session_state.end_time:
        start_datetime = datetime.combine(st.session_state.start_date, st.session_state.start_time)
        end_datetime = datetime.combine(st.session_state.end_date, st.session_state.end_time)
        
        duration = end_datetime - start_datetime
        total_minutes = int(duration.total_seconds() / 60)
        
        if total_minutes > 0:
            days = total_minutes // (24 * 60)
            remaining_minutes = total_minutes % (24 * 60)
            hours = remaining_minutes // 60
            minutes = remaining_minutes % 60
            
            duration_str = ""
            if days > 0:
                duration_str += f"{days}일 "
            if hours > 0:
                duration_str += f"{hours}시간 "
            if minutes > 0:
                duration_str += f"{minutes}분"
            
            st.info(f"⏱️ 총 촬영 시간: {duration_str.strip()}")
        else:
            st.error("⚠️ 종료 일시가 시작 일시보다 이전입니다. 다시 선택해주세요.")

with col2:
    st.header("📋 촬영 예약 요약")
    
    # 매주반복인 경우
    if st.session_state.reservation_type == "매주반복":
        if (st.session_state.selected_days and st.session_state.repeat_start_date and 
            st.session_state.repeat_end_date and st.session_state.start_time and st.session_state.end_time):
            
            # 시간 계산
            start_time_obj = st.session_state.start_time
            end_time_obj = st.session_state.end_time
            
            # 임시 날짜로 duration 계산
            temp_start = datetime.combine(datetime.now().date(), start_time_obj)
            temp_end = datetime.combine(datetime.now().date(), end_time_obj)
            duration = temp_end - temp_start
            total_minutes = int(duration.total_seconds() / 60)
            
            if total_minutes > 0:
                hours = total_minutes // 60
                minutes = total_minutes % 60
                
                # 생성될 예약 개수 계산
                repeat_dates = generate_repeat_dates(
                    st.session_state.repeat_start_date,
                    st.session_state.repeat_end_date,
                    st.session_state.selected_days
                )
                
                st.info(f"""
                **선택하신 반복 예약 정보:**
                
                🔄 **반복 요일:** {', '.join(st.session_state.selected_days)}
                
                📅 **반복 기간:** {st.session_state.repeat_start_date.strftime('%Y년 %m월 %d일')} ~ {st.session_state.repeat_end_date.strftime('%Y년 %m월 %d일')}
                
                ⏰ **촬영 시간:** {start_time_obj.strftime('%H:%M')} ~ {end_time_obj.strftime('%H:%M')}
                
                ⏱️ **1회 촬영 시간:** {hours}시간 {minutes}분
                
                📊 **총 예약 횟수:** {len(repeat_dates)}회
                """)
                
                st.markdown("---")
                
                # 예약 확인 버튼
                if st.button("✅ 촬영 예약 확정", use_container_width=True, type="primary", key="confirm_repeat"):
                    try:
                        # 반복 예약 그룹 저장
                        count = save_repeat_group(
                            selected_days=st.session_state.selected_days,
                            repeat_start_date=st.session_state.repeat_start_date,
                            repeat_end_date=st.session_state.repeat_end_date,
                            start_time=start_time_obj,
                            end_time=end_time_obj,
                            duration_minutes=total_minutes
                        )
                        
                        st.success(f"✨ {count}개의 촬영 예약이 완료되었습니다!")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"예약 저장 중 오류 발생: {str(e)}")
            else:
                st.error("⚠️ 종료 시간이 시작 시간보다 늦어야 합니다.")
        else:
            st.warning("반복 요일, 반복 기간, 촬영 시간을 모두 선택해주세요.")
    
    # 일반예약인 경우
    elif st.session_state.start_date and st.session_state.start_time and st.session_state.end_date and st.session_state.end_time:
        # 촬영 시간 계산
        start_datetime = datetime.combine(st.session_state.start_date, st.session_state.start_time)
        end_datetime = datetime.combine(st.session_state.end_date, st.session_state.end_time)
        
        duration = end_datetime - start_datetime
        total_minutes = int(duration.total_seconds() / 60)
        
        if total_minutes > 0:
            days = total_minutes // (24 * 60)
            remaining_minutes = total_minutes % (24 * 60)
            hours = remaining_minutes // 60
            minutes = remaining_minutes % 60
            
            duration_str = ""
            if days > 0:
                duration_str += f"{days}일 "
            if hours > 0:
                duration_str += f"{hours}시간 "
            if minutes > 0:
                duration_str += f"{minutes}분"
            
            st.info(f"""
            **선택하신 촬영 예약 정보:**
            
            🎬 **촬영 시작**
            📅 {st.session_state.start_date.strftime('%Y년 %m월 %d일')}
            ⏰ {st.session_state.start_time.strftime('%H:%M')}
            
            🎬 **촬영 종료**
            📅 {st.session_state.end_date.strftime('%Y년 %m월 %d일')}
            ⏰ {st.session_state.end_time.strftime('%H:%M')}
            
            ⏱️ **총 촬영 시간:** {duration_str.strip()}
            """)
            
            st.markdown("---")
            
            # 예약 확인 버튼
            if st.button("✅ 촬영 예약 확정", use_container_width=True, type="primary", key="confirm_regular"):
                try:
                    # 일반예약 저장
                    save_reservation(
                        start_date=st.session_state.start_date,
                        start_time=st.session_state.start_time,
                        end_date=st.session_state.end_date,
                        end_time=st.session_state.end_time,
                        duration_minutes=total_minutes
                    )
                    
                    st.success("✨ 촬영 예약이 완료되었습니다!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"예약 저장 중 오류 발생: {str(e)}")
        else:
            st.error("⚠️ 종료 일시가 시작 일시보다 이전입니다.")
    
    else:
        st.warning("촬영 시작/종료 날짜와 시간을 모두 선택해주세요.")

# 예약 내역 표시
st.markdown("---")
st.header("📋 예약 내역")

# 일반예약 조회
reservations_df = get_reservations()
# 반복예약 그룹 조회
repeat_groups_df = get_repeat_groups()

has_data = (not reservations_df.empty) or (not repeat_groups_df.empty)

if has_data:
    # 반복예약 그룹 표시
    if not repeat_groups_df.empty:
        st.subheader("🔄 반복예약")
        for idx, row in repeat_groups_df.iterrows():
            col_display, col_edit, col_delete = st.columns([5, 0.7, 0.7])
            
            with col_display:
                try:
                    days_list = json.loads(row['selected_days'])
                    days_str = ', '.join(days_list)
                except:
                    days_str = "알 수 없음"
                
                # 시간 계산
                duration_mins = row['duration_minutes']
                hours = duration_mins // 60
                minutes = duration_mins % 60
                
                st.info(f"""
                **[매주반복]** 그룹 ID: {row['id']}  
                🔄 **반복 요일:** {days_str}  
                📅 **반복 기간:** {row['repeat_start_date']} ~ {row['repeat_end_date']}  
                ⏰ **촬영 시간:** {row['start_time']} ~ {row['end_time']}  
                ⏱️ **1회 시간:** {hours}시간 {minutes}분  
                📊 **총 {row['total_count']}회 예약**  
                📅 **등록:** {row['created_at']}
                """)
                
                # 개별 예약 상세 보기 (Expander)
                # expander 상태 관리
                is_expanded = (st.session_state.expanded_group_id == row['id'])
                
                with st.expander(f"📋 개별 예약 {row['total_count']}건 상세보기", expanded=is_expanded):
                    # expander가 열리면 세션에 저장
                    if not is_expanded:
                        st.session_state.expanded_group_id = row['id']
                    
                    individual_reservations = get_reservations_by_group(row['id'])
                    
                    if not individual_reservations.empty:
                        # 체크박스 선택을 위한 키 초기화
                        group_key = f"group_{row['id']}"
                        
                        # 모든 예약 ID 리스트
                        all_ids = [int(res['id']) for _, res in individual_reservations.iterrows()]
                        
                        # 전체 선택/해제 버튼
                        col_select_all, col_delete_selected = st.columns([1, 1])
                        
                        with col_select_all:
                            # 현재 체크된 개수 확인 (체크박스 세션 상태 확인)
                            checked_count = sum(1 for res_id in all_ids if st.session_state.get(f"check_ind_{res_id}_{row['id']}", False))
                            all_selected = (checked_count == len(all_ids))
                            
                            if st.button(
                                "☑️ 전체 선택" if not all_selected else "☐️ 전체 해제",
                                key=f"select_all_{row['id']}",
                                use_container_width=True
                            ):
                                # 모든 체크박스 상태 업데이트
                                for res_id in all_ids:
                                    st.session_state[f"check_ind_{res_id}_{row['id']}"] = not all_selected
                                st.rerun()
                        
                        with col_delete_selected:
                            # 현재 선택된 예약 ID 수집
                            selected_ids = [res_id for res_id in all_ids if st.session_state.get(f"check_ind_{res_id}_{row['id']}", False)]
                            selected_count = len(selected_ids)
                            
                            if st.button(
                                f"🗑️ 선택 삭제 ({selected_count})",
                                key=f"delete_selected_{row['id']}",
                                disabled=(selected_count == 0),
                                use_container_width=True,
                                type="primary" if selected_count > 0 else "secondary"
                            ):
                                # 선택된 예약들 삭제
                                for res_id in selected_ids:
                                    delete_individual_reservation(res_id, row['id'])
                                    # 체크박스 상태 초기화
                                    if f"check_ind_{res_id}_{row['id']}" in st.session_state:
                                        del st.session_state[f"check_ind_{res_id}_{row['id']}"]
                                
                                # 남은 예약 확인
                                remaining_reservations = get_reservations_by_group(row['id'])
                                if not remaining_reservations.empty:
                                    st.success(f"✨ {selected_count}개의 예약이 삭제되었습니다! (남은 예약: {len(remaining_reservations)}건)")
                                else:
                                    st.success("✨ 모든 예약이 삭제되어 그룹도 삭제되었습니다!")
                                    st.session_state.expanded_group_id = None
                                
                                st.rerun()
                        
                        st.markdown("---")
                        
                        # 개별 예약 목록
                        for i, res in individual_reservations.iterrows():
                            col_check, col_ind_info, col_ind_del = st.columns([0.5, 4.5, 1])
                            
                            res_id = int(res['id'])
                            
                            with col_check:
                                # 체크박스 - 세션 상태에 직접 저장
                                st.checkbox(
                                    "",
                                    value=False,
                                    key=f"check_ind_{res_id}_{row['id']}",
                                    label_visibility="collapsed"
                                )
                            
                            with col_ind_info:
                                st.markdown(f"""
                                **{i+1}번째 예약**  
                                📅 날짜: {res['start_date']}  
                                ⏰ 시간: {res['start_time']} ~ {res['end_time']}
                                """)
                            
                            with col_ind_del:
                                if st.button("🗑️", key=f"delete_ind_{res['id']}", help="이 예약만 삭제", use_container_width=True):
                                    remaining = delete_individual_reservation(res['id'], row['id'])
                                    
                                    # 체크박스 상태 초기화
                                    if f"check_ind_{res_id}_{row['id']}" in st.session_state:
                                        del st.session_state[f"check_ind_{res_id}_{row['id']}"]
                                    
                                    if remaining > 0:
                                        st.success(f"✨ 개별 예약이 삭제되었습니다! (남은 예약: {remaining}건)")
                                    else:
                                        st.success("✨ 마지막 예약이 삭제되어 그룹도 삭제되었습니다!")
                                        st.session_state.expanded_group_id = None
                                    
                                    st.rerun()
                            
                            st.markdown("---")
                    else:
                        st.warning("개별 예약 데이터가 없습니다.")
            
            with col_edit:
                if st.button("✏️ 수정", key=f"edit_group_{row['id']}", use_container_width=True):
                    st.session_state.editing_group_id = row['id']
                    st.rerun()
            
            with col_delete:
                if st.button("🗑️ 삭제", key=f"delete_group_{row['id']}", use_container_width=True):
                    delete_repeat_group(row['id'])
                    st.session_state.editing_group_id = None
                    st.rerun()
            
            # 수정 모드
            if st.session_state.editing_group_id == row['id']:
                with st.expander("✏️ 반복예약 시간 수정", expanded=True):
                    st.markdown("**🔄 반복 요일 및 기간은 수정할 수 없습니다. 시간만 변경 가능합니다.**")
                    
                    # 기존 시간 파싱
                    try:
                        from datetime import datetime
                        edit_start_time = datetime.strptime(row['start_time'], '%H:%M:%S').time()
                    except:
                        edit_start_time = datetime.strptime(row['start_time'], '%H:%M').time()
                    
                    try:
                        edit_end_time = datetime.strptime(row['end_time'], '%H:%M:%S').time()
                    except:
                        edit_end_time = datetime.strptime(row['end_time'], '%H:%M').time()
                    
                    col_time1, col_sep, col_time2 = st.columns([1, 0.2, 1])
                    
                    with col_time1:
                        new_start_time = st.time_input(
                            "시작 시간",
                            value=edit_start_time,
                            key=f"edit_start_time_group_{row['id']}",
                            step=60
                        )
                    
                    with col_sep:
                        st.markdown("<h4 style='text-align: center; padding-top: 8px;'>~</h4>", unsafe_allow_html=True)
                    
                    with col_time2:
                        new_end_time = st.time_input(
                            "종료 시간",
                            value=edit_end_time,
                            key=f"edit_end_time_group_{row['id']}",
                            step=60
                        )
                    
                    # 시간 계산
                    temp_start = datetime.combine(datetime.now().date(), new_start_time)
                    temp_end = datetime.combine(datetime.now().date(), new_end_time)
                    new_duration = temp_end - temp_start
                    new_total_minutes = int(new_duration.total_seconds() / 60)
                    
                    if new_total_minutes > 0:
                        new_hours = new_total_minutes // 60
                        new_minutes = new_total_minutes % 60
                        st.info(f"⏱️ 변경될 촬영 시간: {new_hours}시간 {new_minutes}분")
                        
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("💾 저장", key=f"save_group_{row['id']}", use_container_width=True, type="primary"):
                                update_repeat_group(
                                    group_id=row['id'],
                                    start_time=new_start_time,
                                    end_time=new_end_time,
                                    duration_minutes=new_total_minutes
                                )
                                st.session_state.editing_group_id = None
                                st.success("✨ 반복예약이 수정되었습니다!")
                                st.rerun()
                        
                        with col_cancel:
                            if st.button("❌ 취소", key=f"cancel_group_{row['id']}", use_container_width=True):
                                st.session_state.editing_group_id = None
                                st.rerun()
                    else:
                        st.error("⚠️ 종료 시간이 시작 시간보다 늦어야 합니다.")
    
    # 일반예약 표시
    if not reservations_df.empty:
        st.subheader("📅 일반예약")
        for idx, row in reservations_df.iterrows():
            col_display, col_edit, col_delete = st.columns([5, 0.7, 0.7])
            
            with col_display:
                # 날짜와 시간 포맷팅
                start_datetime = f"{row['start_date']} {row['start_time']}"
                end_datetime = f"{row['end_date']} {row['end_time']}"
                
                # 총 시간 계산
                duration_mins = row['duration_minutes']
                days = duration_mins // (24 * 60)
                remaining = duration_mins % (24 * 60)
                hours = remaining // 60
                minutes = remaining % 60
                
                duration_str = ""
                if days > 0:
                    duration_str += f"{days}일 "
                if hours > 0:
                    duration_str += f"{hours}시간 "
                if minutes > 0:
                    duration_str += f"{minutes}분"
                
                st.info(f"""
                **[일반예약]** ID: {row['id']}  
                🎬 **촬영 시간:** {start_datetime} ~ {end_datetime}  
                ⏱️ **총 시간:** {duration_str.strip()}  
                📅 **등록:** {row['created_at']}
                """)
            
            with col_edit:
                if st.button("✏️ 수정", key=f"edit_{row['id']}", use_container_width=True):
                    st.session_state.editing_reservation_id = row['id']
                    st.rerun()
            
            with col_delete:
                if st.button("🗑️ 삭제", key=f"delete_{row['id']}", use_container_width=True):
                    delete_reservation(row['id'])
                    st.session_state.editing_reservation_id = None
                    st.rerun()
            
            # 수정 모드
            if st.session_state.editing_reservation_id == row['id']:
                with st.expander("✏️ 예약 수정", expanded=True):
                    # 기존 데이터 파싱
                    try:
                        edit_start_date = datetime.strptime(row['start_date'], '%Y-%m-%d').date()
                        edit_end_date = datetime.strptime(row['end_date'], '%Y-%m-%d').date()
                    except:
                        edit_start_date = datetime.now().date()
                        edit_end_date = datetime.now().date()
                    
                    try:
                        edit_start_time = datetime.strptime(row['start_time'], '%H:%M:%S').time()
                    except:
                        edit_start_time = datetime.strptime(row['start_time'], '%H:%M').time()
                    
                    try:
                        edit_end_time = datetime.strptime(row['end_time'], '%H:%M:%S').time()
                    except:
                        edit_end_time = datetime.strptime(row['end_time'], '%H:%M').time()
                    
                    # 날짜/시간 수정 입력
                    col_date1, col_time1, col_sep2, col_date2, col_time2 = st.columns([2, 1.5, 0.3, 2, 1.5])
                    
                    with col_date1:
                        new_start_date = st.date_input(
                            "시작 날짜",
                            value=edit_start_date,
                            key=f"edit_start_date_{row['id']}"
                        )
                    
                    with col_time1:
                        new_start_time = st.time_input(
                            "시작 시간",
                            value=edit_start_time,
                            key=f"edit_start_time_{row['id']}",
                            step=60
                        )
                    
                    with col_sep2:
                        st.markdown("<h4 style='text-align: center; padding-top: 8px;'>~</h4>", unsafe_allow_html=True)
                    
                    with col_date2:
                        new_end_date = st.date_input(
                            "종료 날짜",
                            value=edit_end_date,
                            min_value=new_start_date,
                            key=f"edit_end_date_{row['id']}"
                        )
                    
                    with col_time2:
                        new_end_time = st.time_input(
                            "종료 시간",
                            value=edit_end_time,
                            key=f"edit_end_time_{row['id']}",
                            step=60
                        )
                    
                    # 시간 계산
                    new_start_dt = datetime.combine(new_start_date, new_start_time)
                    new_end_dt = datetime.combine(new_end_date, new_end_time)
                    new_duration = new_end_dt - new_start_dt
                    new_total_minutes = int(new_duration.total_seconds() / 60)
                    
                    if new_total_minutes > 0:
                        new_days = new_total_minutes // (24 * 60)
                        new_remaining = new_total_minutes % (24 * 60)
                        new_hours = new_remaining // 60
                        new_minutes = new_remaining % 60
                        
                        new_duration_str = ""
                        if new_days > 0:
                            new_duration_str += f"{new_days}일 "
                        if new_hours > 0:
                            new_duration_str += f"{new_hours}시간 "
                        if new_minutes > 0:
                            new_duration_str += f"{new_minutes}분"
                        
                        st.info(f"⏱️ 변경될 촬영 시간: {new_duration_str.strip()}")
                        
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("💾 저장", key=f"save_{row['id']}", use_container_width=True, type="primary"):
                                update_reservation(
                                    reservation_id=row['id'],
                                    start_date=new_start_date,
                                    start_time=new_start_time,
                                    end_date=new_end_date,
                                    end_time=new_end_time,
                                    duration_minutes=new_total_minutes
                                )
                                st.session_state.editing_reservation_id = None
                                st.success("✨ 예약이 수정되었습니다!")
                                st.rerun()
                        
                        with col_cancel:
                            if st.button("❌ 취소", key=f"cancel_{row['id']}", use_container_width=True):
                                st.session_state.editing_reservation_id = None
                                st.rerun()
                    else:
                        st.error("⚠️ 종료 일시가 시작 일시보다 늦어야 합니다.")
else:
    st.info("등록된 예약 내역이 없습니다.")

# 푸터
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <small>촬영 예약 시스템 v1.0 | Powered by Streamlit</small>
</div>
""", unsafe_allow_html=True)
