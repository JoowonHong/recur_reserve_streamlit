"""
촬영 예약 처리 함수 모듈
"""
import sqlite3
import pandas as pd


def print_database_reservation(reservation_id=None, group_id=None):
    """
    데이터베이스에 저장된 예약 정보를 터미널에 출력
    
    Args:
        reservation_id (int, optional): 일반예약 ID
        group_id (int, optional): 반복예약 그룹 ID
    """
    conn = sqlite3.connect('reservations.db')
    
    print("\n" + "="*80)
    print("📋 데이터베이스 예약 정보 출력")
    print("="*80)
    
    if group_id:
        # 반복예약 그룹 정보 출력
        print("\n[반복예약 그룹 테이블]")
        df_group = pd.read_sql_query(
            "SELECT * FROM repeat_groups WHERE id = ?", 
            conn, 
            params=(group_id,)
        )
        print(df_group.to_string(index=False))
        
        print("\n[해당 그룹의 개별 예약 테이블]")
        df_reservations = pd.read_sql_query(
            "SELECT * FROM reservations WHERE repeat_group_id = ? ORDER BY start_date, start_time", 
            conn, 
            params=(group_id,)
        )
        print(df_reservations.to_string(index=False))
        
    elif reservation_id:
        # 일반예약 정보 출력
        print("\n[일반예약 테이블]")
        df = pd.read_sql_query(
            "SELECT * FROM reservations WHERE id = ?", 
            conn, 
            params=(reservation_id,)
        )
        print(df.to_string(index=False))
    
    else:
        # 최신 예약 출력
        print("\n[최신 일반예약]")
        df_latest = pd.read_sql_query(
            "SELECT * FROM reservations WHERE repeat_group_id IS NULL ORDER BY created_at DESC LIMIT 1", 
            conn
        )
        if not df_latest.empty:
            print(df_latest.to_string(index=False))
        else:
            print("일반예약 없음")
        
        print("\n[최신 반복예약 그룹]")
        df_latest_group = pd.read_sql_query(
            "SELECT * FROM repeat_groups ORDER BY created_at DESC LIMIT 1", 
            conn
        )
        if not df_latest_group.empty:
            print(df_latest_group.to_string(index=False))
        else:
            print("반복예약 없음")
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ 데이터베이스 조회 완료")
    print("="*80 + "\n")


def handle_reservation_confirm(reservation_id=None, group_id=None):
    """
    촬영 예약 확정 시 데이터베이스 내용을 출력하는 핸들러
    
    Args:
        reservation_id (int, optional): 일반예약 ID
        group_id (int, optional): 반복예약 그룹 ID
    
    Returns:
        bool: 성공 여부
    """
    try:
        print_database_reservation(reservation_id, group_id)
        return True
    except Exception as e:
        print(f"\n❌ 데이터베이스 조회 중 오류 발생: {str(e)}\n")
        return False
