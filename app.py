import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import sqlite3
import json
from reservation_handler import handle_reservation_confirm
#맥에서 수정 
# 삭제 확인 다이얼로그
@st.dialog("삭제 확인")
def confirm_delete_dialog(message, on_confirm, **kwargs):
    st.warning(f"⚠️ {message}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 확인", use_container_width=True, type="primary"):
            on_confirm(**kwargs)
            st.rerun()
    with col2:
        if st.button("❌ 취소", use_container_width=True):
            st.rerun()

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
            reservation_ids TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 개별 예약 테이블 (테이블이 없을 때만 생성)
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

# 일반 예약 저장
def save_reservation(start_date, start_time, end_date, end_time, duration_minutes):
    conn = sqlite3.connect('reservations.db')
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

# 예약 목록 조회
@st.cache_data(ttl=1)
def get_reservations():
    conn = sqlite3.connect('reservations.db')
    df = pd.read_sql_query(
        "SELECT * FROM reservations ORDER BY created_at DESC", 
        conn
    )
    conn.close()
    return df

# 반복예약 그룹 목록 조회
@st.cache_data(ttl=1)
def get_repeat_groups():
    conn = sqlite3.connect('reservations.db')
    df = pd.read_sql_query("SELECT * FROM repeat_groups ORDER BY created_at DESC", conn)
    conn.close()
    return df

# 특정 반복예약 그룹의 개별 예약 조회
def get_reservations_by_group(group_id):
    print(f"\n📋 get_reservations_by_group 호출: group_id={group_id}")
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    
    # repeat_groups에서 reservation_ids 가져오기
    c.execute("SELECT reservation_ids FROM repeat_groups WHERE id = ?", (group_id,))
    result = c.fetchone()
    
    print(f"   🔍 repeat_groups 조회 결과: {result}")
    
    if result and result[0]:
        reservation_ids = json.loads(result[0])
        print(f"   📝 reservation_ids: {reservation_ids}")
        if reservation_ids:
            placeholders = ','.join('?' * len(reservation_ids))
            query = f"SELECT * FROM reservations WHERE id IN ({placeholders}) ORDER BY start_date, start_time"
            print(f"   🔎 실행 쿼리: {query}")
            print(f"   📊 파라미터: {reservation_ids}")
            df = pd.read_sql_query(query, conn, params=reservation_ids)
            print(f"   ✅ 조회 완료: {len(df)}건")
        else:
            print(f"   ⚠️ reservation_ids가 비어있음")
            df = pd.DataFrame()
    else:
        print(f"   ⚠️ repeat_groups에서 group_id={group_id}를 찾을 수 없음")
        # 존재하지 않는 그룹이면 세션 상태 정리
        if 'expanded_group_id' in st.session_state and st.session_state.expanded_group_id == group_id:
            print(f"   🧹 세션 상태 정리: expanded_group_id={group_id} 제거")
            st.session_state.expanded_group_id = None
        df = pd.DataFrame()
    
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

# 예약 삭제 (일반예약 - repeat_groups 확인)
def delete_reservation(reservation_id):
    print(f"\n🔍 delete_reservation 호출: reservation_id={reservation_id}")
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    
    # 이 예약이 반복예약 그룹에 속하는지 확인
    c.execute("SELECT id, reservation_ids FROM repeat_groups")
    groups = c.fetchall()
    
    print(f"   📦 repeat_groups 검색: {len(groups)}개 그룹")
    
    for group_id, reservation_ids_json in groups:
        if reservation_ids_json:
            try:
                reservation_ids = json.loads(reservation_ids_json)
                print(f"   📋 그룹 {group_id}: {reservation_ids}")
                if reservation_id in reservation_ids:
                    # 반복예약 그룹의 일부라면 delete_individual_reservation 사용
                    print(f"   ✅ 예약 {reservation_id}은 그룹 {group_id}에 속함 → delete_individual_reservation 호출")
                    c.close()
                    conn.close()
                    delete_individual_reservation(reservation_id, group_id)
                    return
            except Exception as e:
                print(f"   ⚠️ JSON 파싱 에러: {e}")
                pass
    
    # 일반 예약이면 그냥 삭제
    print(f"   ℹ️ 일반 예약 → 직접 삭제")
    c.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    conn.commit()
    conn.close()
    print(f"   ✅ 삭제 완료\n")

# 개별 예약 삭제 (반복예약 그룹 내)
def delete_individual_reservation(reservation_id, group_id):
    """개별 예약 삭제 후 그룹의 reservation_ids 업데이트"""
    print(f"\n🗑️ delete_individual_reservation 호출: reservation_id={reservation_id}, group_id={group_id}")
    
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    
    # 개별 예약 삭제
    c.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    print(f"   ✅ reservations 테이블에서 id={reservation_id} 삭제")
    
    # 그룹의 reservation_ids에서 해당 ID 제거
    c.execute("SELECT reservation_ids FROM repeat_groups WHERE id = ?", (group_id,))
    result = c.fetchone()
    
    if result and result[0]:
        reservation_ids = json.loads(result[0])
        print(f"   📋 기존 reservation_ids: {reservation_ids}")
        
        if reservation_id in reservation_ids:
            reservation_ids.remove(reservation_id)
            print(f"   ✂️ {reservation_id} 제거 후: {reservation_ids}")
        
        if reservation_ids:
            # 남은 ID가 있으면 업데이트
            c.execute(
                "UPDATE repeat_groups SET reservation_ids = ? WHERE id = ?",
                (json.dumps(reservation_ids), group_id)
            )
            print(f"   💾 repeat_groups 업데이트: reservation_ids={json.dumps(reservation_ids)}")
            remaining_count = len(reservation_ids)
        else:
            # 모든 개별 예약이 삭제되면 그룹도 삭제
            c.execute("DELETE FROM repeat_groups WHERE id = ?", (group_id,))
            print(f"   🗑️ 모든 예약 삭제됨 - repeat_groups id={group_id} 삭제")
            remaining_count = 0
    else:
        print(f"   ⚠️ repeat_groups에서 reservation_ids를 찾을 수 없음")
        remaining_count = 0
    
    conn.commit()
    conn.close()
    print(f"   ✅ 완료: 남은 예약 {remaining_count}개\n")
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
    
    # reservation_ids에서 ID 목록 가져오기
    c.execute("SELECT reservation_ids FROM repeat_groups WHERE id = ?", (group_id,))
    result = c.fetchone()
    
    if result and result[0]:
        reservation_ids = json.loads(result[0])
        # 관련된 모든 개별 예약의 시간도 업데이트
        for res_id in reservation_ids:
            c.execute('''
                UPDATE reservations 
                SET start_time = ?, end_time = ?, duration_minutes = ?
                WHERE id = ?
            ''', (str(start_time), str(end_time), duration_minutes, res_id))
    
    conn.commit()
    conn.close()

# 반복예약 그룹 삭제 (그룹과 관련된 모든 개별 예약도 삭제)
def delete_repeat_group(group_id):
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    
    # reservation_ids에서 ID 목록 가져오기
    c.execute("SELECT reservation_ids FROM repeat_groups WHERE id = ?", (group_id,))
    result = c.fetchone()
    
    if result and result[0]:
        reservation_ids = json.loads(result[0])
        # 관련된 모든 개별 예약 삭제
        for res_id in reservation_ids:
            c.execute("DELETE FROM reservations WHERE id = ?", (res_id,))
    
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
         duration_minutes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        json.dumps(selected_days),
        str(repeat_start_date),
        str(repeat_end_date),
        str(start_time),
        str(end_time),
        duration_minutes
    ))
    
    group_id = c.lastrowid
    reservation_ids = []
    
    # 각 날짜별로 개별 예약 생성
    for date in dates:
        # 종료 시간이 시작 시간보다 이전이면 다음날로 설정 (자정을 넘어가는 경우)
        if end_time < start_time:
            actual_end_date = date + timedelta(days=1)
        else:
            actual_end_date = date
            
        c.execute('''
            INSERT INTO reservations 
            (start_date, start_time, end_date, end_time, duration_minutes)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(date),
            str(start_time),
            str(actual_end_date),
            str(end_time),
            duration_minutes
        ))
        reservation_ids.append(c.lastrowid)
    
    # reservation_ids를 그룹에 저장
    c.execute(
        "UPDATE repeat_groups SET reservation_ids = ? WHERE id = ?",
        (json.dumps(reservation_ids), group_id)
    )
    
    conn.commit()
    conn.close()
    return group_id, len(dates)

# 페이지 설정
st.set_page_config(
    page_title="촬영 예약 시스템",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 다이얼로그 중앙 정렬 CSS
st.markdown("""
<style>
/* 다이얼로그 오버레이 배경 - 완전히 제거 */
div[data-testid="stModalBackdrop"] {
    display: none !important;
}

/* 다이얼로그 컨테이너 - 여러 선택자 시도 */
section[data-testid="stDialog"],
div[data-testid="stDialog"],
[data-testid="stDialog"] {
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    margin: 0 !important;
    max-height: 90vh !important;
    z-index: 9999 !important;
}

/* Streamlit 다이얼로그 래퍼 */
.stDialog {
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
}
</style>
""", unsafe_allow_html=True)

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
# 추가 옵션 필드
if 'city' not in st.session_state:
    st.session_state.city = None
if 'stadium' not in st.session_state:
    st.session_state.stadium = None
if 'equipment_type' not in st.session_state:
    st.session_state.equipment_type = ""
if 'equipment_name' not in st.session_state:
    st.session_state.equipment_name = ""
if 'is_paid' not in st.session_state:
    st.session_state.is_paid = False
if 'sport_type' not in st.session_state:
    st.session_state.sport_type = None
if 'content_title' not in st.session_state:
    st.session_state.content_title = ""

# 타이틀
st.title("🎬 촬영 예약 시스템")
st.markdown("---")

# 메인 컨텐츠

# 예약 정보 섹션
st.markdown("### 예약 정보")

# 시군구 및 구장 선택
col_city, col_stadium = st.columns(2)

with col_city:
    st.markdown("**🏛️ 시군구**")
    city = st.selectbox(
        "시군구 선택",
        options=["선택하세요", "서울시", "경기도", "인천시", "부산시", "대구시", "대전시", "광주시", "울산시","이동식 구장","기본"],
        key="city_select",
        label_visibility="collapsed"
    )
    st.session_state.city = city if city != "선택하세요" else None

with col_stadium:
    st.markdown("**🏟️ 구장**")
    stadium = st.selectbox(
        "구장 선택",
        options=["선택하세요", "구장A", "구장B", "구장C", "구장D"],
        key="stadium_select",
        label_visibility="collapsed"
    )
    st.session_state.stadium = stadium if stadium != "선택하세요" else None

# 장비 정보
col_eq_type, col_eq_name = st.columns(2)

with col_eq_type:
    st.markdown("**🎥 장비타입**")
    equipment_type = st.text_input(
        "장비타입 입력",
        value=st.session_state.equipment_type,
        # placeholder="예: 카메라, 드론, 조명 등",
        key="equipment_type_input",
        label_visibility="collapsed"
    )
    st.session_state.equipment_type = equipment_type

with col_eq_name:
    st.markdown("**📷 장비 이름**")
    equipment_name = st.text_input(
        "장비 이름 입력",
        value=st.session_state.equipment_name,
        # placeholder="예: Sony A7S3, DJI Mini 3 Pro 등",
        key="equipment_name_input",
        label_visibility="collapsed"
    )
    st.session_state.equipment_name = equipment_name

# # 금액 및 종목
# col_price, col_sport = st.columns(2)




# with col_sport:
#     st.markdown("**⚽ 종목선택**")
#     sport_type = st.selectbox(
#         "종목 선택",
#         options=["선택하세요", "축구", "농구", "배구", "야구", "테니스", "배드민턴", "핸드볼"],
#         key="sport_select",
#         label_visibility="collapsed"
#     )
#     st.session_state.sport_type = sport_type if sport_type != "선택하세요" else None

# st.markdown("---")

# 장비 정보


# 예약 유형 선택
st.markdown("**📅 예약일자**")
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
    # st.markdown("**🔄 반복 요일 선택**")
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
    # st.markdown("**🔄 반복 기간**")
    min_date = datetime.now().date()
    max_date = min_date + timedelta(days=90)
    col_repeat1, col_repeat_sep, col_repeat2 = st.columns([1, 0.2, 1])
    with col_repeat1:
        # 세션 상태 값이 있으면 그것을 사용, 없으면 기본값
        repeat_start_value = st.session_state.repeat_start_date if st.session_state.repeat_start_date else min_date
        repeat_start_date = st.date_input(
            "반복 시작 날짜",
            min_value=min_date,
            max_value=max_date,
            value=repeat_start_value,
            key="repeat_start_date_input",
            label_visibility="collapsed"
        )
        st.session_state.repeat_start_date = repeat_start_date
    with col_repeat_sep:
        st.markdown("<h4 style='text-align: center; padding-top: 8px;'>~</h4>", unsafe_allow_html=True)
    with col_repeat2:
        # 세션 상태 값이 있으면 그것을 사용, 없으면 시작 날짜
        repeat_end_value = st.session_state.repeat_end_date if st.session_state.repeat_end_date else (repeat_start_date if repeat_start_date else min_date)
        repeat_end_date = st.date_input(
            "반복 종료 날짜",
            min_value=repeat_start_date if repeat_start_date else min_date,
            max_value=max_date,
            value=repeat_end_value,
            key="repeat_end_date_input",
            label_visibility="collapsed"
        )
        st.session_state.repeat_end_date = repeat_end_date

    # st.markdown("---")

    # st.markdown("### 촬영 시간")
    # st.markdown📅 촬영 일시 선택")

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
    # st.markdown("**📅 시작 날짜**")
    if is_repeat:
        # 매주반복일 때는 비활성화
        st.text_input(
            "촬영 시작 날짜",
            value="0000/00/00",
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
    # st.markdown("**⏰ 시작 시간**")
    start_time = st.time_input(
        "촬영 시작 시간",
        value=current_time,
        key="start_time_input",
        label_visibility="collapsed",
        step=60  # 1분 단위
    )
    
    # 시작 시간이 변경되었는지 확인하고 즉시 종료 시간 업데이트
    if 'prev_start_time' not in st.session_state:
        st.session_state.prev_start_time = start_time
        st.session_state.end_time_key = 0
    
    if st.session_state.prev_start_time != start_time:
        st.session_state.prev_start_time = start_time
        # 종료 시간을 자동으로 계산하여 세션에 저장
        new_end_date, new_end_time = calculate_end_datetime(start_date, start_time, 3)
        st.session_state.end_time = new_end_time
        st.session_state.end_date = new_end_date
        # 위젯 키 증가하여 새 위젯 생성
        st.session_state.end_time_key += 1
        st.rerun()
    
    st.session_state.start_time = start_time
# 시작 시간 + 3시간 계산
default_end_date, default_end_time = calculate_end_datetime(start_date, start_time, 3)
with col_separator:
    st.markdown("<div style='display: flex; align-items: center; justify-content: center; height: 100%;'><h3 style='text-align: center; margin: 0; padding-top: 12px;'>~</h3></div>", unsafe_allow_html=True)
with col1_3:
    # st.markdown("**📅 종료 날짜**")
    if is_repeat:
        # 매주반복일 때는 비활성화
        st.text_input(
            "촬영 종료 날짜",
            value="0000/00/00",
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
    # st.markdown("**⏰ 종료 시간**")
    # 동적 키를 사용하여 시작 시간 변경 시 위젯 재생성
    end_time_key = f"end_time_input_{st.session_state.get('end_time_key', 0)}"
    
    end_time = st.time_input(
        "촬영 종료 시간",
        value=st.session_state.end_time,
        key=end_time_key,
        label_visibility="collapsed",
        step=60  # 1분 단위
    )
    st.session_state.end_time = end_time
# 종료 시간 유효성 검사 (자정을 넘어가는 경우 고려)
if start_date and start_time and end_date and end_time:
    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, end_time)
    
    # 매주반복일 때는 종료 시간이 시작 시간보다 이전이면 다음날로 간주
    if is_repeat and end_time < start_time:
        # 자정을 넘어가는 경우로 간주하여 시작 날짜 기준 다음날로 설정
        end_datetime = datetime.combine(start_date + timedelta(days=1), end_time)
    elif end_datetime <= start_datetime:
        st.warning("⚠️ 종료 일시가 시작 일시보다 늦어야 합니다.")
# 촬영 시간 계산 및 표시
if st.session_state.start_date and st.session_state.start_time and st.session_state.end_date and st.session_state.end_time:
    start_datetime = datetime.combine(st.session_state.start_date, st.session_state.start_time)
    end_datetime = datetime.combine(st.session_state.end_date, st.session_state.end_time)
    
    # 매주반복일 때 종료 시간이 시작 시간보다 이전이면 다음날로 간주
    if is_repeat and st.session_state.end_time < st.session_state.start_time:
        # 시작 날짜 기준으로 다음날로 설정
        end_datetime = datetime.combine(st.session_state.start_date + timedelta(days=1), st.session_state.end_time)
    
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

# 금액
st.markdown("**💵 금액**")
price_option = st.radio(
    "금액 선택",
    options=["무료", "유료"],
    horizontal=True,
    key="price_option",
    label_visibility="collapsed"
)
st.session_state.is_paid = (price_option == "유료")
st.markdown("---")

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
        
        # 종료 시간이 시작 시간보다 이전이면 다음날로 간주 (자정을 넘어가는 경우)
        if end_time_obj < start_time_obj:
            temp_end = datetime.combine(datetime.now().date() + timedelta(days=1), end_time_obj)
        
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
                # 예약 가능 여부 판단
                check_dates = generate_repeat_dates(
                    st.session_state.repeat_start_date,
                    st.session_state.repeat_end_date,
                    st.session_state.selected_days
                )
                
                if len(check_dates) == 0:
                    # 예약이 없는 경우 팝업
                    @st.dialog("예약 불가")
                    def no_reservation_dialog():
                        st.error("⚠️ 해당하는 구간에 예약이 없습니다. 다시 설정해주세요.")
                        st.markdown("""
                        **확인사항:**
                        - 선택한 요일이 반복 기간 내에 존재하는지 확인해주세요.
                        - 반복 시작 날짜와 종료 날짜를 확인해주세요.
                        """)
                        if st.button("✅ 확인", use_container_width=True, type="primary"):
                            st.rerun()
                    no_reservation_dialog()
                else:
                    # 예약 진행
                    try:
                        group_id, count = save_repeat_group(
                            selected_days=st.session_state.selected_days,
                            repeat_start_date=st.session_state.repeat_start_date,
                            repeat_end_date=st.session_state.repeat_end_date,
                            start_time=start_time_obj,
                            end_time=end_time_obj,
                            duration_minutes=total_minutes
                        )
                        
                        # 터미널에 데이터베이스 내용 출력
                        handle_reservation_confirm(group_id=group_id)
                        
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
        
        # st.markdown("---")
        
        # 예약 확인 버튼
        if st.button("✅ 촬영 예약 확정", use_container_width=True, type="primary", key="confirm_regular"):
            try:
                # 일반예약 저장
                reservation_id = save_reservation(
                    start_date=st.session_state.start_date,
                    start_time=st.session_state.start_time,
                    end_date=st.session_state.end_date,
                    end_time=st.session_state.end_time,
                    duration_minutes=total_minutes
                )
                
                # 터미널에 데이터베이스 내용 출력
                handle_reservation_confirm(reservation_id=reservation_id)
                
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
                
                # reservation_ids에서 개수 계산
                try:
                    reservation_ids = json.loads(row['reservation_ids']) if row['reservation_ids'] else []
                    total_count = len(reservation_ids)
                except:
                    total_count = 0
                
                st.info(f"""
                **[매주반복]** 그룹 ID: {row['id']}  
                🔄 **반복 요일:** {days_str}  
                📅 **반복 기간:** {row['repeat_start_date']} ~ {row['repeat_end_date']}  
                ⏰ **촬영 시간:** {row['start_time']} ~ {row['end_time']}  
                ⏱️ **1회 시간:** {hours}시간 {minutes}분  
                📊 **총 {total_count}회 예약**  
                📅 **등록:** {row['created_at']}
                """)
                
                # 개별 예약 상세 보기 (Expander)
                # expander 상태 관리
                is_expanded = (st.session_state.expanded_group_id == row['id'])
                
                with st.expander(f"📋 개별 예약 {total_count}건 상세보기", expanded=is_expanded):
                    # expander가 열리면 세션에 저장
                    if not is_expanded:
                        st.session_state.expanded_group_id = row['id']
                    
                    try:
                        individual_reservations = get_reservations_by_group(row['id'])
                    except Exception as e:
                        st.error(f"❌ 데이터베이스 조회 중 오류 발생: {str(e)}")
                        individual_reservations = pd.DataFrame()
                    
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
                                @st.dialog("삭제 확인")
                                def confirm_dialog(count, ids, group_id):
                                    st.warning(f"⚠️ {count}개의 예약을 삭제하시겠습니까?")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button("✅ 확인", use_container_width=True, type="primary", key="conf_sel_yes"):
                                            # 선택된 예약들 삭제
                                            for res_id in ids:
                                                delete_individual_reservation(res_id, group_id)
                                                # 체크박스 상태 초기화
                                                if f"check_ind_{res_id}_{group_id}" in st.session_state:
                                                    del st.session_state[f"check_ind_{res_id}_{group_id}"]
                                            
                                            # 남은 예약 확인
                                            remaining_reservations = get_reservations_by_group(group_id)
                                            if remaining_reservations.empty:
                                                st.session_state.expanded_group_id = None
                                            st.rerun()
                                    with col2:
                                        if st.button("❌ 취소", use_container_width=True, key="conf_sel_no"):
                                            st.rerun()
                                confirm_dialog(selected_count, selected_ids, row['id'])
                        
                        st.markdown("---")
                        
                        # 개별 예약 목록
                        for i, res in individual_reservations.iterrows():
                            col_check, col_ind_info, col_ind_del = st.columns([0.5, 4.5, 1])
                            
                            res_id = int(res['id'])
                            
                            # 총 시간 계산
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
                            
                            with col_check:
                                # 체크박스 - 세션 상태에 직접 저장
                                st.checkbox(
                                    "Select reservation",
                                    value=False,
                                    key=f"check_ind_{res_id}_{row['id']}",
                                    label_visibility="collapsed"
                                )
                            
                            with col_ind_info:
                                st.info(f"""
                                **[매주반복-개별]** ID: {res['id']}  
                                🎬 **촬영 시간:** {start_datetime} ~ {end_datetime}  
                                ⏱️ **총 시간:** {duration_str.strip()}  
                                📅 **등록:** {res['created_at']}
                                """)
                            
                            with col_ind_del:
                                if st.button("🗑️", key=f"delete_ind_{res['id']}", help="이 예약만 삭제", use_container_width=True):
                                    @st.dialog("삭제 확인")
                                    def confirm_ind_dialog(reservation_id, group_id, check_key):
                                        st.warning("⚠️ 이 예약을 삭제하시겠습니까?")
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.button("✅ 확인", use_container_width=True, type="primary", key="conf_ind_yes"):
                                                delete_individual_reservation(reservation_id, group_id)
                                                if check_key in st.session_state:
                                                    del st.session_state[check_key]
                                                st.rerun()
                                        with col2:
                                            if st.button("❌ 취소", use_container_width=True, key="conf_ind_no"):
                                                st.rerun()
                                    confirm_ind_dialog(res['id'], row['id'], f"check_ind_{res_id}_{row['id']}")
                            
                            st.markdown("---")
                    else:
                        st.warning("개별 예약 데이터가 없습니다.")
            
            with col_edit:
                if st.button("✏️ 수정", key=f"edit_group_{row['id']}", use_container_width=True):
                    st.session_state.editing_group_id = row['id']
                    st.rerun()
            
            with col_delete:
                if st.button("🗑️ 삭제", key=f"delete_group_{row['id']}", use_container_width=True):
                    @st.dialog("삭제 확인")
                    def confirm_group_dialog(group_id, reservation_ids_json):
                        try:
                            reservation_ids = json.loads(reservation_ids_json) if reservation_ids_json else []
                            count = len(reservation_ids)
                        except:
                            count = 0
                        st.warning(f"⚠️ 반복예약 그룹 ({count}개 예약)을 삭제하시겠습니까?")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ 확인", use_container_width=True, type="primary", key="conf_grp_yes"):
                                delete_repeat_group(group_id)
                                st.session_state.editing_group_id = None
                                # expanded_group_id도 초기화
                                if 'expanded_group_id' in st.session_state:
                                    st.session_state.expanded_group_id = None
                                st.rerun()
                        with col2:
                            if st.button("❌ 취소", use_container_width=True, key="conf_grp_no"):
                                st.rerun()
                    confirm_group_dialog(row['id'], row['reservation_ids'])
            
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
                                
                                # 터미널에 수정된 데이터베이스 내용 출력
                                from reservation_handler import handle_reservation_confirm
                                handle_reservation_confirm(group_id=row['id'])
                                
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
                    @st.dialog("삭제 확인")
                    def confirm_res_dialog(reservation_id):
                        st.warning("⚠️ 이 예약을 삭제하시겠습니까?")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ 확인", use_container_width=True, type="primary", key="conf_res_yes"):
                                delete_reservation(reservation_id)
                                st.session_state.editing_reservation_id = None
                                st.rerun()
                        with col2:
                            if st.button("❌ 취소", use_container_width=True, key="conf_res_no"):
                                st.rerun()
                    confirm_res_dialog(row['id'])
            
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
                                
                                # 터미널에 수정된 데이터베이스 내용 출력
                                from reservation_handler import handle_reservation_confirm
                                handle_reservation_confirm(reservation_id=row['id'])
                                
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

# 데이터베이스 조회 버튼
st.header("🧪 개발 도구")
if st.button("📊 데이터베이스 조회", help="전체 데이터베이스 내용을 터미널에 출력합니다", use_container_width=True):
    print("\n" + "="*80)
    print("📊 데이터베이스 전체 조회 (reservations.db)")
    print("="*80)
    
    conn = sqlite3.connect('reservations.db')
    
    # 예약 테이블
    print("\n[reservations 테이블]")
    df_reservations = pd.read_sql_query("SELECT * FROM reservations ORDER BY id DESC LIMIT 30", conn)
    if not df_reservations.empty:
        print(df_reservations.to_string(index=False))
    else:
        print("데이터 없음")
    
    # 반복예약 그룹 테이블
    print("\n[repeat_groups 테이블]")
    df_groups = pd.read_sql_query("SELECT * FROM repeat_groups ORDER BY id DESC LIMIT 20", conn)
    if not df_groups.empty:
        print(df_groups.to_string(index=False))
    else:
        print("데이터 없음")
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ 데이터베이스 조회 완료")
    print("="*80 + "\n")
    
    st.success("✅ 데이터베이스 내용이 터미널에 출력되었습니다!")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <small>촬영 예약 시스템 v1.0 | Powered by Streamlit</small>
</div>
""", unsafe_allow_html=True)
