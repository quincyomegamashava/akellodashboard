import pymysql

def test_purchases_query():
    # Credentials from app/routes.py
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
            # Query updated to match implementation but with LIMIT
            query = """
                SELECT 
                    b.id,
                    b.title, 
                    b.author,
                    b.isbn,
                    SUM(bo.quantity) as purchase_count
                FROM books b
                JOIN book_order bo ON b.id = bo.book_id
                JOIN orders o ON bo.order_id = o.id
                WHERE o.payment_method != 'Voucher'
                  AND o.status = 'Completed'
                GROUP BY b.id, b.title, b.author, b.isbn
                ORDER BY purchase_count DESC
                LIMIT 10
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            print("\nTop 10 Purchased Books (No Vouchers):")
            print("-" * 65)
            print(f"{'Qty':>6} | {'Title'}")
            print("-" * 65)
            for row in results:
                print(f"{row['purchase_count']:>6} | {row['title']} by {row['author']}")
            print("-" * 65)
            
        conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_purchases_query()
