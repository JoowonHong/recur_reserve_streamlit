import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

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

# 페이지 설정
st.set_page_config(
    page_title="촬영 예약 시스템",
    page_icon="🎬",
    layout="wide"
)

# 세션 상태 초기화
if 'start_date' not in st.session_state:
    st.session_state.start_date = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'end_date' not in st.session_state:
    st.session_state.end_date = None
if 'end_time' not in st.session_state:
    st.session_state.end_time = None

# 타이틀
st.title("🎬 촬영 예약 시스템")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("촬영 예약 정보")
    st.markdown("### 🎬 촬영 시작")
    if st.session_state.start_date:
        st.success(f"📅 날짜: {st.session_state.start_date}")
    if st.session_state.start_time:
        st.success(f"⏰ 시간: {st.session_state.start_time}")
    
    st.markdown("### 🎬 촬영 종료")
    if st.session_state.end_date:
        st.success(f"📅 날짜: {st.session_state.end_date}")
    if st.session_state.end_time:
        st.success(f"⏰ 시간: {st.session_state.end_time}")

# 메인 컨텐츠
col1, col2 = st.columns([2, 1])

with col1:
    st.header("1️⃣ 촬영 시작 일시 선택")
    
    # 날짜 선택 (오늘부터 90일 후까지)
    min_date = datetime.now().date()
    max_date = min_date + timedelta(days=90)
    
    # 현재 시간 기반 기본값
    current_time = get_current_time()
    
    col_start1, col_start2 = st.columns(2)
    
    with col_start1:
        st.markdown("### 📅 시작 날짜")
        start_date = st.date_input(
            "촬영 시작 날짜",
            min_value=min_date,
            max_value=max_date,
            value=min_date,
            key="start_date_input",
            label_visibility="collapsed"
        )
        st.session_state.start_date = start_date
    
    with col_start2:
        st.markdown("### ⏰ 시작 시간")
        start_time = st.time_input(
            "촬영 시작 시간",
            value=current_time,
            key="start_time_input",
            label_visibility="collapsed",
            step=60  # 1분 단위
        )
        st.session_state.start_time = start_time
    
    st.markdown("---")
    
    # 종료 일시 선택
    st.header("2️⃣ 촬영 종료 일시 선택")
    
    # 시작 시간 + 3시간 계산
    default_end_date, default_end_time = calculate_end_datetime(start_date, start_time, 3)
    
    col_end1, col_end2 = st.columns(2)
    
    with col_end1:
        st.markdown("### 📅 종료 날짜")
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
    
    with col_end2:
        st.markdown("### ⏰ 종료 시간")
        end_time = st.time_input(
            "촬영 종료 시간",
            value=default_end_time,
            key="end_time_input",
            label_visibility="collapsed",
            step=60  # 1분 단위
        )
        st.session_state.end_time = end_time
        
        # 종료 시간 유효성 검사
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
    
    if st.session_state.start_date and st.session_state.start_time and st.session_state.end_date and st.session_state.end_time:
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
            if st.button("✅ 촬영 예약 확정", use_container_width=True, type="primary"):
                st.success("✨ 촬영 예약이 완료되었습니다!")
                st.balloons()
        else:
            st.error("⚠️ 종료 일시가 시작 일시보다 이전입니다.")
            
    else:
        st.warning("촬영 시작/종료 날짜와 시간을 모두 선택해주세요.")

# 푸터
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <small>촬영 예약 시스템 v1.0 | Powered by Streamlit</small>
</div>
""", unsafe_allow_html=True)
