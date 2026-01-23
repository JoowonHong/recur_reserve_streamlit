"""
촬영 예약 처리 함수 모듈
"""
import sqlite3
import pandas as pd
import json


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
        # repeat_groups에서 reservation_ids 가져오기
        c = conn.cursor()
        c.execute("SELECT reservation_ids FROM repeat_groups WHERE id = ?", (group_id,))
        result = c.fetchone()
        
        if result and result[0]:
            reservation_ids = json.loads(result[0])
            if reservation_ids:
                placeholders = ','.join('?' * len(reservation_ids))
                query = f"SELECT * FROM reservations WHERE id IN ({placeholders}) ORDER BY start_date, start_time"
                df_reservations = pd.read_sql_query(query, conn, params=reservation_ids)
                print(df_reservations.to_string(index=False))
            else:
                print("개별 예약 없음")
        else:
            print("개별 예약 없음")
        
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
        print("\n[최신 일반예약 (개별)]")
        # 반복예약 그룹에 속하지 않는 예약 확인
        c = conn.cursor()
        c.execute("SELECT GROUP_CONCAT(reservation_ids) FROM repeat_groups WHERE reservation_ids IS NOT NULL")
        result = c.fetchone()
        
        all_group_ids = []
        if result and result[0]:
            # 모든 그룹의 reservation_ids를 수집
            for ids_json in result[0].split(','):
                try:
                    ids = json.loads(ids_json)
                    all_group_ids.extend(ids)
                except:
                    pass
        
        if all_group_ids:
            placeholders = ','.join('?' * len(all_group_ids))
            query = f"SELECT * FROM reservations WHERE id NOT IN ({placeholders}) ORDER BY created_at DESC LIMIT 1"
            df_latest = pd.read_sql_query(query, conn, params=all_group_ids)
        else:
            df_latest = pd.read_sql_query("SELECT * FROM reservations ORDER BY created_at DESC LIMIT 1", conn)
        
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
