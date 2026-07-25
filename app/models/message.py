"""
消息数据库模型。

SQLAlchemy ORM 模型，记录会话中的单条消息，
包含发送角色、内容、Token 用量等字段。
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    sender = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    message_type = Column(String(20), default="text")
    
    # 关系
    conversation = relationship("Conversation", back_populates="messages") 