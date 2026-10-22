import database

if __name__ == "__main__":
    print("Testing database query functionality...")
    
    # Test query with no filters
    results = database.query_records()
    print(f"Query returned {len(results)} records")
    
    if results:
        print("First record:")
        print(results[0])
    else:
        print("No records found")
    
    print("Test completed.")
