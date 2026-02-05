import pymysql

def check_analytics_schema():
    host = '40.88.149.15'
    port = 33000
    user = 'kmudzimuirema'
    password = 'Ak3110$2022'
    database = 'akello_library'
    
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=10
        )
        
        with conn.cursor() as cursor:
            for table in ['orders', 'book_order', 'book_user', 'books']:
                print(f"\n--- {table} schema ---")
                cursor.execute(f"DESCRIBE {table}")
                cols = cursor.fetchall()
                for c in cols:
                    print(f"{c['Field']}: {c['Type']}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_analytics_schema()
