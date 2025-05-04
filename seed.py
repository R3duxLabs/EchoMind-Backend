import asyncio
import os
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Media, MilestoneLog, Relationship, SessionLog, SummaryLog, User

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def gen_id():
    return str(uuid.uuid4())

async def seed():
    async with AsyncSessionLocal() as session:
        suffix = datetime.utcnow().strftime("%H%M%S")

        # Users
        user1 = User(id=gen_id(), email=f"test_{suffix}@echomind.ai", name="Echo Tester", role="individual", therapist_agent="Echo", active_mode="reflect")
        user2 = User(id=gen_id(), email=f"parent_{suffix}@echomind.ai", name="Parent Pilot", role="parent", therapist_agent="Elora", active_mode="parenting")
        user3 = User(id=gen_id(), email=f"admin_{suffix}@echomind.ai", name="Admin Agent", role="admin", therapist_agent="Bridge", active_mode="system")

        session.add_all([user1, user2, user3])
        await session.commit()

        # SessionLog
        session_log = SessionLog(id=gen_id(), user_id=user1.id, agent="Echo", session_data={"messages": ["Hello", "How are you?"]}, timestamp=datetime.utcnow())
        session.add(session_log)

        # Milestone
        milestone = MilestoneLog(id=gen_id(), user_id=user1.id, agent="Echo", type="growth", description="Set a boundary for the first time", timestamp=datetime.utcnow())
        session.add(milestone)

        # Summary
        summary = SummaryLog(id=gen_id(), user_id=user1.id, agent="Echo", summary_text="User is showing progress.", tags=["hope", "progress"], emotional_tone="hopeful", confidence=0.92, timestamp=datetime.utcnow())
        session.add(summary)

        # Media
        media = Media(id=gen_id(), title="Guide to Boundaries", url="https://echomind.ai/sample", tags=["emotional regulation"], agent="Echo", media_type="article", source="curated", timestamp=datetime.utcnow())
        session.add(media)

        # Relationship
        relationship = Relationship(id=gen_id(), user_a_id=user2.id, user_b_id=user1.id, relationship_type="parent", approved=True, visibility_level="summary", visibility_rules='{"can_view":"milestones"}')
        session.add(relationship)

        await session.commit()
        print("✅ Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed())
