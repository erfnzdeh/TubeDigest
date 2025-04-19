from sqlalchemy import inspect
from dotenv import load_dotenv
from src.database.connection import get_engine

def main():
    # Load environment variables
    load_dotenv()
    
    # Get the database engine
    engine = get_engine()
    
    # Create inspector
    inspector = inspect(engine)
    
    # Get all table names
    tables = inspector.get_table_names()
    print("\nTables in database:")
    print("==================")
    for table in tables:
        print(f"\n{table}:")
        # Get columns for each table
        columns = inspector.get_columns(table)
        for column in columns:
            print(f"  - {column['name']}: {column['type']}")

if __name__ == "__main__":
    main() 