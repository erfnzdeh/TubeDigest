from src.database.connection import engine, Base
from src.models.user import User
from src.models.channel import Channel
from src.models.video import Video

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db() 