from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from src.database.connection import Base

class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True)
    youtube_id = Column(String(20), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    channel_id = Column(Integer, ForeignKey('channels.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    channel = relationship("Channel", back_populates="videos") 