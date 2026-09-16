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


def check_analytics_schema():
    try:
        conn = library_connect()

        with conn.cursor() as cursor:
            for table in ['orders', 'book_order', 'book_user', 'books']:
                print(f"\n--- {table} schema ---")
                cursor.execute(f"DESCRIBE {table}")
                cols = cursor.fetchall()
                for c in cols:
                    print(f"{c['Field']}: {c['Type']}")

        conn.close()
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_analytics_schema()
