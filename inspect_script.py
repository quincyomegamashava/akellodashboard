from app.routes import get_ruzivo_conn

def inspect_table(table_name):
    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()
        print(f"--- Inspecting {table_name} ---")
        cursor.execute(f"DESCRIBE {table_name}")
        for col in cursor.fetchall():
            print(col)
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error describing {table_name}: {e}")

inspect_table("tblpoints_purchase")
inspect_table("tblscholarships_schools")
