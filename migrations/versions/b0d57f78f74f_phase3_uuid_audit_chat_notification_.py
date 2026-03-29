"""phase3_uuid_audit_chat_notification_attendance_public

Revision ID: b0d57f78f74f
Revises: cf6b6076f44b
Create Date: 2026-03-29 12:56:42.945344

"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4


# revision identifiers, used by Alembic.
revision = 'b0d57f78f74f'
down_revision = 'cf6b6076f44b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('chat_rooms', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('chat_rooms', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('chat_rooms', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('chat_rooms', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('chat_messages', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('chat_messages', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('chat_messages', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('chat_messages', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('notifications', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('notifications', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('notifications', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('notifications', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('attendance_sessions', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('attendance_sessions', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('attendance_sessions', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('attendance_sessions', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('attendance_records', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('attendance_records', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('attendance_records', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('attendance_records', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('news', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('news', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('news', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('testimonials', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('testimonials', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('testimonials', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('testimonials', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('contact_messages', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('contact_messages', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('contact_messages', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('contact_messages', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    conn = op.get_bind()

    rows = conn.execute(sa.text('SELECT id, created_at FROM chat_rooms')).mappings().all()
    for row in rows:
        conn.execute(sa.text(
            'UPDATE chat_rooms SET uuid=:uuid, updated_at=COALESCE(updated_at, :dt, CURRENT_TIMESTAMP), '
            'is_deleted=COALESCE(is_deleted, 0) WHERE id=:id'
        ), {'uuid': str(uuid4()), 'dt': row['created_at'], 'id': row['id']})

    rows = conn.execute(sa.text('SELECT id, created_at FROM chat_messages')).mappings().all()
    for row in rows:
        conn.execute(sa.text(
            'UPDATE chat_messages SET uuid=:uuid, updated_at=COALESCE(updated_at, :dt, CURRENT_TIMESTAMP), '
            'is_deleted=COALESCE(is_deleted, 0) WHERE id=:id'
        ), {'uuid': str(uuid4()), 'dt': row['created_at'], 'id': row['id']})

    rows = conn.execute(sa.text('SELECT id, created_at FROM notifications')).mappings().all()
    for row in rows:
        conn.execute(sa.text(
            'UPDATE notifications SET uuid=:uuid, updated_at=COALESCE(updated_at, :dt, CURRENT_TIMESTAMP), '
            'is_deleted=COALESCE(is_deleted, 0) WHERE id=:id'
        ), {'uuid': str(uuid4()), 'dt': row['created_at'], 'id': row['id']})

    rows = conn.execute(sa.text('SELECT id, created_at FROM attendance_sessions')).mappings().all()
    for row in rows:
        conn.execute(sa.text(
            'UPDATE attendance_sessions SET uuid=:uuid, updated_at=COALESCE(updated_at, :dt, CURRENT_TIMESTAMP), '
            'is_deleted=COALESCE(is_deleted, 0) WHERE id=:id'
        ), {'uuid': str(uuid4()), 'dt': row['created_at'], 'id': row['id']})

    rows = conn.execute(sa.text('SELECT id, marked_at FROM attendance_records')).mappings().all()
    for row in rows:
        conn.execute(sa.text(
            'UPDATE attendance_records SET uuid=:uuid, updated_at=COALESCE(updated_at, :dt, CURRENT_TIMESTAMP), '
            'is_deleted=COALESCE(is_deleted, 0) WHERE id=:id'
        ), {'uuid': str(uuid4()), 'dt': row['marked_at'], 'id': row['id']})

    rows = conn.execute(sa.text('SELECT id FROM news')).mappings().all()
    for row in rows:
        conn.execute(sa.text(
            'UPDATE news SET uuid=:uuid, is_deleted=COALESCE(is_deleted, 0) WHERE id=:id'
        ), {'uuid': str(uuid4()), 'id': row['id']})

    rows = conn.execute(sa.text('SELECT id, created_at FROM testimonials')).mappings().all()
    for row in rows:
        conn.execute(sa.text(
            'UPDATE testimonials SET uuid=:uuid, updated_at=COALESCE(updated_at, :dt, CURRENT_TIMESTAMP), '
            'is_deleted=COALESCE(is_deleted, 0) WHERE id=:id'
        ), {'uuid': str(uuid4()), 'dt': row['created_at'], 'id': row['id']})

    rows = conn.execute(sa.text('SELECT id, created_at FROM contact_messages')).mappings().all()
    for row in rows:
        conn.execute(sa.text(
            'UPDATE contact_messages SET uuid=:uuid, updated_at=COALESCE(updated_at, :dt, CURRENT_TIMESTAMP), '
            'is_deleted=COALESCE(is_deleted, 0) WHERE id=:id'
        ), {'uuid': str(uuid4()), 'dt': row['created_at'], 'id': row['id']})

    with op.batch_alter_table('chat_rooms') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_chat_rooms_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_chat_rooms_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('chat_messages') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_chat_messages_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_chat_messages_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('notifications') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_notifications_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_notifications_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('attendance_sessions') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_attendance_sessions_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_attendance_sessions_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('attendance_records') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_attendance_records_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_attendance_records_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('news') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_news_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_news_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('testimonials') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_testimonials_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_testimonials_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('contact_messages') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_contact_messages_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_contact_messages_is_deleted', ['is_deleted'], unique=False)


def downgrade():
    with op.batch_alter_table('contact_messages') as batch_op:
        batch_op.drop_index('ix_contact_messages_is_deleted')
        batch_op.drop_index('ix_contact_messages_uuid')
    op.drop_column('contact_messages', 'deleted_at')
    op.drop_column('contact_messages', 'is_deleted')
    op.drop_column('contact_messages', 'updated_at')
    op.drop_column('contact_messages', 'uuid')

    with op.batch_alter_table('testimonials') as batch_op:
        batch_op.drop_index('ix_testimonials_is_deleted')
        batch_op.drop_index('ix_testimonials_uuid')
    op.drop_column('testimonials', 'deleted_at')
    op.drop_column('testimonials', 'is_deleted')
    op.drop_column('testimonials', 'updated_at')
    op.drop_column('testimonials', 'uuid')

    with op.batch_alter_table('news') as batch_op:
        batch_op.drop_index('ix_news_is_deleted')
        batch_op.drop_index('ix_news_uuid')
    op.drop_column('news', 'deleted_at')
    op.drop_column('news', 'is_deleted')
    op.drop_column('news', 'uuid')

    with op.batch_alter_table('attendance_records') as batch_op:
        batch_op.drop_index('ix_attendance_records_is_deleted')
        batch_op.drop_index('ix_attendance_records_uuid')
    op.drop_column('attendance_records', 'deleted_at')
    op.drop_column('attendance_records', 'is_deleted')
    op.drop_column('attendance_records', 'updated_at')
    op.drop_column('attendance_records', 'uuid')

    with op.batch_alter_table('attendance_sessions') as batch_op:
        batch_op.drop_index('ix_attendance_sessions_is_deleted')
        batch_op.drop_index('ix_attendance_sessions_uuid')
    op.drop_column('attendance_sessions', 'deleted_at')
    op.drop_column('attendance_sessions', 'is_deleted')
    op.drop_column('attendance_sessions', 'updated_at')
    op.drop_column('attendance_sessions', 'uuid')

    with op.batch_alter_table('notifications') as batch_op:
        batch_op.drop_index('ix_notifications_is_deleted')
        batch_op.drop_index('ix_notifications_uuid')
    op.drop_column('notifications', 'deleted_at')
    op.drop_column('notifications', 'is_deleted')
    op.drop_column('notifications', 'updated_at')
    op.drop_column('notifications', 'uuid')

    with op.batch_alter_table('chat_messages') as batch_op:
        batch_op.drop_index('ix_chat_messages_is_deleted')
        batch_op.drop_index('ix_chat_messages_uuid')
    op.drop_column('chat_messages', 'deleted_at')
    op.drop_column('chat_messages', 'is_deleted')
    op.drop_column('chat_messages', 'updated_at')
    op.drop_column('chat_messages', 'uuid')

    with op.batch_alter_table('chat_rooms') as batch_op:
        batch_op.drop_index('ix_chat_rooms_is_deleted')
        batch_op.drop_index('ix_chat_rooms_uuid')
    op.drop_column('chat_rooms', 'deleted_at')
    op.drop_column('chat_rooms', 'is_deleted')
    op.drop_column('chat_rooms', 'updated_at')
    op.drop_column('chat_rooms', 'uuid')
