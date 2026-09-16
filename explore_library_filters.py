import os
import pymysql
from dotenv import load_dotenv

load_dotenv()


def library_connect():
    host = os.getenv('AL_DB_HOST')
    user = os.getenv('AL_DB_USER')
    password = os.getenv('AL_DB_PASS')
    database = os.getenv('AL_DB_NAME', 'akello_library')
    port = int(os.getenv('AL_DB_PORT') or '3306')
    if not host or not user or password is None:
        raise SystemExit('Set AL_DB_HOST, AL_DB_USER, and AL_DB_PASS in .env')
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
    )


def explore_library_schema():
    try:
        conn = library_connect()

        with conn.cursor() as cursor:
            print("--- Genres ---")
            cursor.execute("SELECT id, name FROM genres ORDER BY name")
            genres = cursor.fetchall()
            for g in genres:
                print(f"{g['id']}: {g['name']}")

            print("\n--- Other Tables ---")
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            for t in tables:
                table_name = list(t.values())[0]
                if any(keyword in table_name.lower() for keyword in ['cat', 'level', 'type', 'grade', 'subject']):
                    print(f"Potential filter table: {table_name}")

        conn.close()
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    explore_library_schema()
