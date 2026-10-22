import database

if __name__ == "__main__":
    print("Running database initialization to fix missing columns...")
    database.init_db()
    print("Database fix completed.")
