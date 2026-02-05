from app.routes import get_ruzivo_conn

def inspect_table(table_name):
    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()
        print(f"--- Inspecting {table_name} Columns ---")
        cursor.execute(f"DESCRIBE {table_name}")
        cols = [c['Field'] if isinstance(c, dict) else c[0] for c in cursor.fetchall()]
        print(cols)
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error describing {table_name}: {e}")

inspect_table("tblstudents")
inspect_table("tblstudent_info")
