from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel

class Summary(BaseModel):
    __tablename__ = 'summaries'

    video_id = Column(String(255), nullable=False)
    video_title = Column(String(255))
    video_url = Column(String(255))
    summary_text = Column(Text)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    channel_id = Column(Integer, ForeignKey('channels.id'), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="summaries")
    channel = relationship("Channel", back_populates="summaries") 