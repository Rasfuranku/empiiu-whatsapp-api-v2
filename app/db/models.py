from sqlalchemy import Column, String, JSON, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class Entrepreneur(Base):
    __tablename__ = "entrepreneurs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String, index=True)
    current_category = Column(String, default="IDEATION")
    profile_data = Column(JSON, default={})
    question_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    messages = relationship("Message", back_populates="entrepreneur", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entrepreneur_id = Column(Integer, ForeignKey("entrepreneurs.id"))
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    entrepreneur = relationship("Entrepreneur", back_populates="messages")
