import pymysql

def explore_library_schema():
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
            # Get all genres
            print("--- Genres ---")
            cursor.execute("SELECT id, name FROM genres ORDER BY name")
            genres = cursor.fetchall()
            for g in genres:
                print(f"{g['id']}: {g['name']}")
            
            # Check for other potential filter tables
            print("\n--- Other Tables ---")
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            for t in tables:
                table_name = list(t.values())[0]
                if any(keyword in table_name.lower() for keyword in ['cat', 'level', 'type', 'grade', 'subject']):
                    print(f"Potential filter table: {table_name}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    explore_library_schema()
