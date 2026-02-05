import os
import pymysql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_query():
    # Use credentials from app/routes.py for testing
    host = '40.88.149.15'
    port = 33000
    user = 'kmudzimuirema'
    password = 'Ak3110$2022'
    database = 'akello_library'
    
    print(f"Connecting to {database} at {host}:{port}...")
    
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
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_query()
