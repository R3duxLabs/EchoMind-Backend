import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

def gen_id():
    return str(uuid.uuid4())

class UserRole(str, enum.Enum):
    individual = "individual"
    parent = "parent"
    child = "child"
    expert = "expert"
    admin = "admin"

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    email = Column(String, unique=True)
    name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.individual)
    created_at = Column(DateTime, default=datetime.utcnow)
    therapist_agent = Column(String)
    active_mode = Column(String, default="individual")
    subscription_tier = Column(String, default="free")

    sessions = relationship("SessionLog", back_populates="user")
    summaries = relationship("MemorySnapshot", back_populates="user")
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    milestones = relationship("MilestoneLog", back_populates="user")

class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    therapist_name = Column(String)
    tone_preference = Column(String)
    pacing_preference = Column(String)
    media_preference = Column(JSON)
    learning_style = Column(String)
    active_core_agent = Column(String, default="EchoMind")
    last_updated = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="settings")

class MemorySnapshot(Base):
    __tablename__ = "memory_snapshots"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"))
    agent = Column(String)
    summary_text = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="summaries")

class SessionLog(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"))
    session_data = Column(JSON)
    agent = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")

class SummaryLog(Base):
    __tablename__ = "summary_logs"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"))
    agent = Column(String)
    summary_text = Column(Text)
    tags = Column(ARRAY(String))
    emotional_tone = Column(String)
    confidence = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class SwitchLog(Base):
    __tablename__ = "switch_logs"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"))
    from_agent = Column(String)
    to_agent = Column(String)
    reason = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Media(Base):
    __tablename__ = "media"
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String)
    url = Column(String)
    tags = Column(ARRAY(String))
    agent = Column(String)
    media_type = Column(String)
    source = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class MilestoneType(str, enum.Enum):
    insight = "insight"
    boundary = "boundary"
    regulation = "regulation"
    growth = "growth"

class MilestoneLog(Base):
    __tablename__ = "milestone_logs"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"))
    agent = Column(String)
    type = Column(Enum(MilestoneType))
    description = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="milestones")

class Relationship(Base):
    __tablename__ = "relationships"
    id = Column(String, primary_key=True, default=gen_id)
    user_a_id = Column(String)
    user_b_id = Column(String)
    relationship_type = Column(String)
    approved = Column(Boolean, default=False)
    visibility_level = Column(String, default="summary")
    visibility_rules = Column(Text)
