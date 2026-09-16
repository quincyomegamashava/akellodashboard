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


def test_query():
    print("Connecting to library DB via AL_DB_* ...")

    try:
        conn = library_connect()

        with conn.cursor() as cursor:
            query = """
                SELECT 
                    b.id,
                    b.title, 
                    b.author,
                    b.isbn,
                    COUNT(bu.id) as subscription_count
                FROM books b
                LEFT JOIN book_user bu ON b.id = bu.book_id
                GROUP BY b.id, b.title, b.author, b.isbn
                HAVING subscription_count > 0
                ORDER BY subscription_count DESC
                LIMIT 10
            """
            cursor.execute(query)
            results = cursor.fetchall()

            print("\nTop 10 Subscribed Books:")
            print("-" * 60)
            for row in results:
                print(f"{row['subscription_count']:>5} | {row['title']} by {row['author']}")
            print("-" * 60)

        conn.close()
        return True
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_query()
