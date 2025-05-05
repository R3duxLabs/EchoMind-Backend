import enum
import uuid
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    JSON
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

Base = declarative_base()

def gen_id() -> str:
    return str(uuid.uuid4())

# ---------------------- ENUMS ----------------------
class UserRole(str, enum.Enum):
    individual = "individual"
    parent = "parent"
    child = "child"
    expert = "expert"
    admin = "admin"

class MilestoneType(str, enum.Enum):
    insight = "insight"
    boundary = "boundary"
    regulation = "regulation"
    growth = "growth"
    
class RelationshipType(str, enum.Enum):
    parent_child = "parent_child"
    therapist_patient = "therapist_patient"
    mentor_mentee = "mentor_mentee"
    friend = "friend"
    
class VisibilityLevel(str, enum.Enum):
    none = "none"
    summary = "summary"
    full = "full"
    custom = "custom"

class FeedbackType(str, enum.Enum):
    session = "session"
    suggestion = "suggestion" 
    bug = "bug"
    feature = "feature"

class BridgeStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    paused = "paused"
    completed = "completed"
    rejected = "rejected"

class AgentType(str, enum.Enum):
    therapist = "therapist"
    coach = "coach"
    parent = "parent"
    friend = "friend"
    bridge = "bridge"
    system = "system"
    assistant = "assistant"
    expert = "expert"
    critic = "critic"
    creative = "creative"
    mediator = "mediator"

# ---------------------- BASE MIXINS ----------------------
class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class UserRelatedMixin:
    """Mixin for entities related to a user"""
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent = Column(String, nullable=False, default="EchoMind", index=True)

# ---------------------- USERS ----------------------
class User(Base, TimestampMixin):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=gen_id)
    email = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.individual, nullable=False)
    therapist_agent = Column(String)
    active_mode = Column(String, default="individual")
    subscription_tier = Column(String, default="free")
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    sessions = relationship("SessionLog", back_populates="user", cascade="all, delete-orphan")
    memory_snapshots = relationship("MemorySnapshot", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="joined")
    milestones = relationship("MilestoneLog", back_populates="user", cascade="all, delete-orphan")
    summary_logs = relationship("SummaryLog", back_populates="user", cascade="all, delete-orphan")
    
    # Relationships where user is user_a
    initiated_relationships = relationship(
        "Relationship", 
        foreign_keys="Relationship.user_a_id",
        back_populates="user_a",
        cascade="all, delete-orphan"
    )
    
    # Relationships where user is user_b
    received_relationships = relationship(
        "Relationship", 
        foreign_keys="Relationship.user_b_id",
        back_populates="user_b",
        cascade="all, delete-orphan"
    )
    
    # Bridge sessions
    bridge_sessions_as_initiator = relationship(
        "BridgeSession",
        foreign_keys="BridgeSession.initiator_id",
        back_populates="initiator",
        cascade="all, delete-orphan"
    )
    
    bridge_sessions_as_participant = relationship(
        "BridgeSession",
        foreign_keys="BridgeSession.participant_id",
        back_populates="participant",
        cascade="all, delete-orphan"
    )
    
    # Usage stats
    usage_stats = relationship("UsageStats", back_populates="user", cascade="all, delete-orphan")
    
    # Personality preferences
    personality_preferences = relationship("UserPersonalityPreference", back_populates="user", cascade="all, delete-orphan")
    personality_adaptations = relationship("PersonalityAdaptation", back_populates="user", cascade="all, delete-orphan")
    
    @validates('email')
    def validate_email(self, key, email):
        if email:
            email = email.lower().strip()
        return email

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, role={self.role})>"

# ---------------------- USER SETTINGS ----------------------
class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"
    
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    therapist_name = Column(String)
    tone_preference = Column(String)
    pacing_preference = Column(String)
    media_preference = Column(ARRAY(String), default=[])
    learning_style = Column(String)
    active_core_agent = Column(String, default="EchoMind")
    preferences = Column(JSON, default={})
    notifications_enabled = Column(Boolean, default=True)

    user = relationship("User", back_populates="settings")
    
    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, agent={self.active_core_agent})>"

# ---------------------- MEMORY ----------------------
class MemorySnapshot(Base, UserRelatedMixin, TimestampMixin):
    __tablename__ = "memory_snapshots"
    
    id = Column(String, primary_key=True, default=gen_id)
    summary_text = Column(Text, nullable=False)
    memory_type = Column(String, default="general")
    is_shared = Column(Boolean, default=False)
    version = Column(Integer, default=1)

    user = relationship("User", back_populates="memory_snapshots")
    
    __table_args__ = (
        Index('idx_memory_user_agent', 'user_id', 'agent'),
    )
    
    def __repr__(self):
        return f"<MemorySnapshot(id={self.id}, user_id={self.user_id}, agent={self.agent})>"

# ---------------------- SESSION ----------------------
class SessionLog(Base, UserRelatedMixin, TimestampMixin):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, default=gen_id)
    session_data = Column(JSON, nullable=False)
    session_length = Column(Float)  # Duration in seconds
    session_tokens = Column(Integer)
    
    user = relationship("User", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_sessions_user_timestamp', 'user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SessionLog(id={self.id}, user_id={self.user_id}, agent={self.agent})>"

# ---------------------- SUMMARY LOG ----------------------
class SummaryLog(Base, UserRelatedMixin, TimestampMixin):
    __tablename__ = "summary_logs"
    
    id = Column(String, primary_key=True, default=gen_id)
    summary_text = Column(Text, nullable=False)
    tags = Column(ARRAY(String), default=[])
    emotional_tone = Column(String)
    confidence = Column(Float)
    related_session_id = Column(String, ForeignKey("sessions.id", ondelete="SET NULL"))
    
    user = relationship("User", back_populates="summary_logs")
    related_session = relationship("SessionLog")
    
    __table_args__ = (
        Index('idx_summary_user_timestamp', 'user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SummaryLog(id={self.id}, user_id={self.user_id}, agent={self.agent})>"

# ---------------------- AGENT SWITCH LOG ----------------------
class SwitchLog(Base, TimestampMixin):
    __tablename__ = "switch_logs"
    
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    from_agent = Column(String, nullable=False)
    to_agent = Column(String, nullable=False)
    reason = Column(Text)
    triggered_by = Column(String, default="system")  # system, user, agent
    
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_switch_user_timestamp', 'user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SwitchLog(id={self.id}, user={self.user_id}, from={self.from_agent}, to={self.to_agent})>"

# ---------------------- MEDIA ----------------------
class Media(Base, TimestampMixin):
    __tablename__ = "media"
    
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    tags = Column(ARRAY(String), default=[])
    agent = Column(String, nullable=False, default="EchoMind")
    media_type = Column(String, nullable=False)  # audio, video, image, pdf, etc.
    source = Column(String)
    description = Column(Text)
    duration = Column(Float)  # For audio/video, in seconds
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"))
    
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_media_type_tags', 'media_type', postgresql_using='gin', postgresql_ops={'tags': 'gin_array_ops'}),
    )
    
    def __repr__(self):
        return f"<Media(id={self.id}, title={self.title}, type={self.media_type})>"

# ---------------------- MILESTONE LOG ----------------------
class MilestoneLog(Base, UserRelatedMixin, TimestampMixin):
    __tablename__ = "milestone_logs"
    
    id = Column(String, primary_key=True, default=gen_id)
    milestone_type = Column(Enum(MilestoneType), nullable=False)
    description = Column(Text, nullable=False)
    importance = Column(Integer, default=1)  # 1-5 scale
    related_session_id = Column(String, ForeignKey("sessions.id", ondelete="SET NULL"))
    
    user = relationship("User", back_populates="milestones")
    related_session = relationship("SessionLog")
    
    __table_args__ = (
        Index('idx_milestone_user_type', 'user_id', 'milestone_type'),
    )
    
    def __repr__(self):
        return f"<MilestoneLog(id={self.id}, user={self.user_id}, type={self.milestone_type})>"

# ---------------------- RELATIONSHIPS ----------------------
class Relationship(Base, TimestampMixin):
    __tablename__ = "relationships"
    
    id = Column(String, primary_key=True, default=gen_id)
    user_a_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_b_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(Enum(RelationshipType), nullable=False)
    approved = Column(Boolean, default=False, nullable=False)
    visibility_level = Column(Enum(VisibilityLevel), default=VisibilityLevel.summary, nullable=False)
    visibility_rules = Column(JSON, default={})
    notes = Column(Text)
    
    # Define relationships to both users
    user_a = relationship("User", foreign_keys=[user_a_id], back_populates="initiated_relationships")
    user_b = relationship("User", foreign_keys=[user_b_id], back_populates="received_relationships")
    
    __table_args__ = (
        UniqueConstraint('user_a_id', 'user_b_id', 'relationship_type', name='uix_relationship'),
        Index('idx_relationship_users', 'user_a_id', 'user_b_id'),
    )
    
    def __repr__(self):
        return f"<Relationship(id={self.id}, type={self.relationship_type}, a={self.user_a_id}, b={self.user_b_id})>"

# ---------------------- USER FEEDBACK ----------------------
class UserFeedback(Base, UserRelatedMixin, TimestampMixin):
    __tablename__ = "user_feedback"
    
    id = Column(String, primary_key=True, default=gen_id)
    feedback_type = Column(Enum(FeedbackType), nullable=False)
    content = Column(Text, nullable=False)
    rating = Column(Integer)  # 1-5 scale
    related_session_id = Column(String, ForeignKey("sessions.id", ondelete="SET NULL"))
    status = Column(String, default="new")  # new, reviewed, implemented, rejected
    
    user = relationship("User")
    related_session = relationship("SessionLog")
    
    __table_args__ = (
        Index('idx_feedback_user_type', 'user_id', 'feedback_type'),
    )
    
    def __repr__(self):
        return f"<UserFeedback(id={self.id}, type={self.feedback_type}, user={self.user_id})>"

# ---------------------- USAGE STATS ----------------------
class UsageStats(Base):
    __tablename__ = "usage_stats"
    
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, default=func.current_date())
    sessions_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_session_time = Column(Float, default=0.0)  # In seconds
    agents_used = Column(ARRAY(String), default=[])
    
    user = relationship("User", back_populates="usage_stats")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uix_user_date_stats'),
    )
    
    def __repr__(self):
        return f"<UsageStats(user={self.user_id}, date={self.date}, tokens={self.total_tokens})>"

# ---------------------- AGENT DEFINITION ----------------------
class AgentDefinition(Base, TimestampMixin):
    __tablename__ = "agent_definitions"
    
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    type = Column(Enum(AgentType), nullable=False)
    system_prompt = Column(Text, nullable=False)
    tone_profile = Column(JSON, nullable=False)
    capabilities = Column(ARRAY(String), default=[])
    emoji = Column(String)
    version = Column(String, nullable=False, default="1.0.0")
    is_active = Column(Boolean, default=True)
    
    # Reference to the personality profile used by this agent
    personality_profile_id = Column(String, ForeignKey("personality_profiles.id", ondelete="SET NULL"))
    
    # Agents should be versioned, and this allows for referencing previous versions
    previous_version_id = Column(String, ForeignKey("agent_definitions.id", ondelete="SET NULL"))
    
    # Relationship to previous version
    previous_version = relationship("AgentDefinition", remote_side=[id])
    personality_profile = relationship("PersonalityProfile")
    
    __table_args__ = (
        Index('idx_agent_name_version', 'name', 'version'),
    )
    
    def __repr__(self):
        return f"<AgentDefinition(name={self.name}, version={self.version})>"

# ---------------------- PERSONALITY PROFILES ----------------------
class PersonalityTrait(str, enum.Enum):
    """Enumeration of personality traits that can be assigned to agents."""
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    EMPATHETIC = "empathetic"
    DIRECT = "direct"
    SUPPORTIVE = "supportive"
    CHALLENGING = "challenging"
    ADAPTABLE = "adaptable"
    STRUCTURED = "structured"
    DETAILED = "detailed"
    CONCISE = "concise"
    FORMAL = "formal"
    CASUAL = "casual"
    OPTIMISTIC = "optimistic"
    REALISTIC = "realistic"
    CURIOUS = "curious"
    PATIENT = "patient"

class CommunicationStyle(str, enum.Enum):
    """Enumeration of communication styles for agent responses."""
    SOCRATIC = "socratic"  # Asks questions to guide thinking
    INSTRUCTIVE = "instructive"  # Provides direct guidance
    COLLABORATIVE = "collaborative"  # Works with user as a partner
    COACHING = "coaching"  # Encourages and guides growth
    TECHNICAL = "technical"  # Focuses on technical precision
    ACCESSIBLE = "accessible"  # Simplifies complex topics
    NARRATIVE = "narrative"  # Uses stories and examples
    METHODICAL = "methodical"  # Step-by-step approach

class EmotionalTone(str, enum.Enum):
    """Emotional tone for agent communication."""
    NEUTRAL = "neutral"
    ENTHUSIASTIC = "enthusiastic"
    CALM = "calm"
    ENCOURAGING = "encouraging"
    REASSURING = "reassuring"
    AUTHORITATIVE = "authoritative"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"

class PersonalityProfile(Base, TimestampMixin):
    """Database model for personality profiles."""
    __tablename__ = "personality_profiles"
    
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    
    # Primary attributes
    primary_traits = Column(ARRAY(String), nullable=False)
    secondary_traits = Column(ARRAY(String), default=[])
    communication_style = Column(Enum(CommunicationStyle), nullable=False)
    emotional_tone = Column(Enum(EmotionalTone), nullable=False)
    
    # Compatible agent types
    compatible_agent_types = Column(ARRAY(String), nullable=False)
    
    # Response modifiers
    verbosity_level = Column(Float, nullable=False, default=0.5)
    technical_level = Column(Float, nullable=False, default=0.5)
    formality_level = Column(Float, nullable=False, default=0.5)
    
    # Dynamic adaptation settings
    adapts_to_user = Column(Boolean, default=True)
    adaptation_rate = Column(Float, default=0.2)
    
    # Prompt modifiers
    prompt_modifiers = Column(JSON, default={})
    
    # System fields
    is_system = Column(Boolean, default=False)
    version = Column(String, default="1.0.0")
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_personality_name', 'name'),
        UniqueConstraint('name', 'version', name='uix_personality_version'),
    )
    
    def __repr__(self):
        return f"<PersonalityProfile(name={self.name}, style={self.communication_style})>"

class UserPersonalityPreference(Base, TimestampMixin):
    """Records user preferences for agent personalities."""
    __tablename__ = "user_personality_preferences"
    
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Preferred personality traits and settings
    preferred_traits = Column(ARRAY(String), default=[])
    communication_style_preference = Column(Enum(CommunicationStyle))
    emotional_tone_preference = Column(Enum(EmotionalTone))
    verbosity_preference = Column(Float)
    technical_level_preference = Column(Float)
    formality_preference = Column(Float)
    
    # Agent-specific preferences
    agent_specific_preferences = Column(JSON, default={})
    
    # Relationship
    user = relationship("User", back_populates="personality_preferences")
    
    __table_args__ = (
        Index('idx_user_personality_pref', 'user_id'),
    )
    
    def __repr__(self):
        return f"<UserPersonalityPreference(user_id={self.user_id})>"

class PersonalityAdaptation(Base, TimestampMixin):
    """Tracks adaptations to personality profiles for specific users."""
    __tablename__ = "personality_adaptations"
    
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_type = Column(Enum(AgentType), nullable=False)
    base_profile_id = Column(String, ForeignKey("personality_profiles.id", ondelete="CASCADE"), nullable=False)
    
    # Adapted parameters
    adapted_traits = Column(ARRAY(String))
    adapted_verbosity = Column(Float)
    adapted_technical_level = Column(Float)
    adapted_formality = Column(Float)
    adapted_prompt_modifiers = Column(JSON, default={})
    
    # Adaptation metadata
    adaptation_reason = Column(Text)
    interaction_metrics = Column(JSON, default={})
    
    # Relationships
    user = relationship("User", back_populates="personality_adaptations")
    base_profile = relationship("PersonalityProfile")
    
    __table_args__ = (
        Index('idx_personality_adaptation_user', 'user_id', 'agent_type'),
        UniqueConstraint('user_id', 'agent_type', 'base_profile_id', name='uix_user_agent_profile'),
    )
    
    def __repr__(self):
        return f"<PersonalityAdaptation(user_id={self.user_id}, agent_type={self.agent_type})>"

# ---------------------- BRIDGE SESSION ----------------------
class BridgeSession(Base, TimestampMixin):
    __tablename__ = "bridge_sessions"
    
    id = Column(String, primary_key=True, default=gen_id)
    initiator_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(BridgeStatus), default=BridgeStatus.pending, nullable=False)
    topic = Column(String)
    context = Column(JSON, default={})
    memory_timeframe_start = Column(DateTime(timezone=True))
    memory_timeframe_end = Column(DateTime(timezone=True))
    intervention_level = Column(Integer, default=2)  # 1-5 scale, with 1 being minimal and 5 being maximal
    notes = Column(Text)
    ended_at = Column(DateTime(timezone=True))
    
    # Relationships
    initiator = relationship("User", foreign_keys=[initiator_id], back_populates="bridge_sessions_as_initiator")
    participant = relationship("User", foreign_keys=[participant_id], back_populates="bridge_sessions_as_participant")
    
    # Bridge messages
    messages = relationship("BridgeMessage", back_populates="session", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_bridge_users', 'initiator_id', 'participant_id'),
        Index('idx_bridge_status', 'status'),
    )
    
    def __repr__(self):
        return f"<BridgeSession(id={self.id}, initiator={self.initiator_id}, participant={self.participant_id}, status={self.status})>"

# ---------------------- BRIDGE MESSAGE ----------------------
class BridgeMessage(Base, TimestampMixin):
    __tablename__ = "bridge_messages"
    
    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("bridge_sessions.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_text = Column(Text, nullable=False)
    translated_text = Column(Text)
    emotional_tone = Column(String)
    confidence = Column(Float)
    intervention_applied = Column(Boolean, default=False)
    intervention_type = Column(String)
    intervention_reason = Column(Text)
    
    # Relationships
    session = relationship("BridgeSession", back_populates="messages")
    sender = relationship("User")
    
    __table_args__ = (
        Index('idx_bridge_message_session', 'session_id'),
        Index('idx_bridge_message_sender', 'sender_id'),
    )
    
    def __repr__(self):
        return f"<BridgeMessage(id={self.id}, session={self.session_id}, sender={self.sender_id})>"