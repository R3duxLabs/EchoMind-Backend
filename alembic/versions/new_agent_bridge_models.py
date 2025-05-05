"""Add AgentDefinition and Bridge models

Revision ID: 28910db54321
Revises: bf7764b3197d
Create Date: 2023-05-05 10:12:34.567890

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '28910db54321'
down_revision = 'bf7764b3197d'
branch_labels = None
depends_on = None


def upgrade():
    # Create BridgeStatus enum type
    bridge_status = postgresql.ENUM('pending', 'active', 'paused', 'completed', 'rejected', name='bridgestatus')
    bridge_status.create(op.get_bind())

    # Create AgentType enum type
    agent_type = postgresql.ENUM('therapist', 'coach', 'parent', 'friend', 'bridge', 'system', name='agenttype')
    agent_type.create(op.get_bind())

    # Create agent_definitions table
    op.create_table('agent_definitions',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('type', sa.Enum('therapist', 'coach', 'parent', 'friend', 'bridge', 'system', name='agenttype'), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('tone_profile', sa.JSON(), nullable=False),
        sa.Column('capabilities', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('emoji', sa.String(), nullable=True),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('previous_version_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['previous_version_id'], ['agent_definitions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_agent_name_version', 'agent_definitions', ['name', 'version'], unique=False)

    # Create bridge_sessions table
    op.create_table('bridge_sessions',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('initiator_id', sa.String(), nullable=False),
        sa.Column('participant_id', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'active', 'paused', 'completed', 'rejected', name='bridgestatus'), nullable=False),
        sa.Column('topic', sa.String(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('memory_timeframe_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('memory_timeframe_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('intervention_level', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['initiator_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['participant_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_bridge_status', 'bridge_sessions', ['status'], unique=False)
    op.create_index('idx_bridge_users', 'bridge_sessions', ['initiator_id', 'participant_id'], unique=False)

    # Create bridge_messages table
    op.create_table('bridge_messages',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('sender_id', sa.String(), nullable=False),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('translated_text', sa.Text(), nullable=True),
        sa.Column('emotional_tone', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('intervention_applied', sa.Boolean(), nullable=True),
        sa.Column('intervention_type', sa.String(), nullable=True),
        sa.Column('intervention_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['bridge_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_bridge_message_sender', 'bridge_messages', ['sender_id'], unique=False)
    op.create_index('idx_bridge_message_session', 'bridge_messages', ['session_id'], unique=False)

    # Add index to user_feedback table
    op.create_index('idx_feedback_user_type', 'user_feedback', ['user_id', 'feedback_type'], unique=False)


def downgrade():
    # Drop the indexes
    op.drop_index('idx_feedback_user_type', table_name='user_feedback')
    op.drop_index('idx_bridge_message_session', table_name='bridge_messages')
    op.drop_index('idx_bridge_message_sender', table_name='bridge_messages')
    op.drop_index('idx_bridge_users', table_name='bridge_sessions')
    op.drop_index('idx_bridge_status', table_name='bridge_sessions')
    op.drop_index('idx_agent_name_version', table_name='agent_definitions')
    
    # Drop the tables
    op.drop_table('bridge_messages')
    op.drop_table('bridge_sessions')
    op.drop_table('agent_definitions')
    
    # Drop the enum types
    op.execute('DROP TYPE agenttype')
    op.execute('DROP TYPE bridgestatus')