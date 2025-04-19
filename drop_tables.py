from sqlalchemy import inspect
from dotenv import load_dotenv
from src.database.connection import get_engine, Base

def main():
    # Load environment variables
    load_dotenv()
    
    # Get the database engine
    engine = get_engine()
    
    # Drop all tables
    Base.metadata.drop_all(engine)
    print("All tables dropped successfully!")

if __name__ == "__main__":
    main() 