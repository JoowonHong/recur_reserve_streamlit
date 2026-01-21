import sqlite3
import pandas as pd

def inspect_database(db_path='reservations.db'):
    """데이터베이스의 전체 구조와 데이터를 확인"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    print("=" * 80)
    print("📊 데이터베이스 전체 구조 분석")
    print("=" * 80)
    print()
    
    # 1. 테이블 목록 조회
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in c.fetchall()]
    
    print(f"📋 테이블 개수: {len(tables)}")
    print(f"📋 테이블 목록: {', '.join(tables)}")
    print()
    
    # 2. 각 테이블의 상세 정보
    for table in tables:
        print("=" * 80)
        print(f"🗂️  테이블: {table}")
        print("=" * 80)
        
        # 테이블 스키마 조회
        c.execute(f"PRAGMA table_info({table});")
        columns = c.fetchall()
        
        print("\n📐 테이블 구조:")
        print("-" * 80)
        print(f"{'번호':<5} {'컬럼명':<25} {'타입':<15} {'NULL허용':<10} {'기본값':<15} {'PK':<5}")
        print("-" * 80)
        
        for col in columns:
            col_id, name, col_type, not_null, default_val, pk = col
            null_str = "NOT NULL" if not_null else "NULL"
            default_str = str(default_val) if default_val else "-"
            pk_str = "PK" if pk else ""
            print(f"{col_id:<5} {name:<25} {col_type:<15} {null_str:<10} {default_str:<15} {pk_str:<5}")
        
        print()
        
        # Foreign Key 정보 조회
        c.execute(f"PRAGMA foreign_key_list({table});")
        fks = c.fetchall()
        if fks:
            print("🔗 외래키(Foreign Key):")
            print("-" * 80)
            for fk in fks:
                fk_id, seq, ref_table, from_col, to_col, on_update, on_delete, match = fk
                print(f"   {from_col} → {ref_table}({to_col})")
            print()
        
        # 데이터 개수 조회
        c.execute(f"SELECT COUNT(*) FROM {table};")
        count = c.fetchone()[0]
        print(f"📊 데이터 개수: {count}행")
        print()
        
        # 데이터 샘플 (최대 5개)
        if count > 0:
            print("📄 데이터 샘플 (최대 5개):")
            print("-" * 80)
            df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 5", conn)
            print(df.to_string())
            print()
            
            # 통계 정보 (숫자 컬럼)
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
            if len(numeric_cols) > 0:
                print("📈 숫자 컬럼 통계:")
                print("-" * 80)
                print(df[numeric_cols].describe().to_string())
                print()
        
        print()
    
    conn.close()
    
    print("=" * 80)
    print("✅ 분석 완료")
    print("=" * 80)

if __name__ == "__main__":
    inspect_database()