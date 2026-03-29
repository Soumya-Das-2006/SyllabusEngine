"""add_uuid_and_audit_to_users_subjects

Revision ID: 5496ce7a44d9
Revises: 
Create Date: 2026-03-29 12:46:11.711549

"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4


# revision identifiers, used by Alembic.
revision = '5496ce7a44d9'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('users', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('subjects', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('subjects', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('subjects', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('subjects', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    conn = op.get_bind()

    user_rows = conn.execute(sa.text('SELECT id, created_at FROM users')).mappings().all()
    for row in user_rows:
        conn.execute(
            sa.text(
                'UPDATE users '
                'SET uuid = :uuid, '
                'updated_at = COALESCE(updated_at, :created_at, CURRENT_TIMESTAMP), '
                'is_deleted = COALESCE(is_deleted, 0) '
                'WHERE id = :id'
            ),
            {
                'uuid': str(uuid4()),
                'created_at': row['created_at'],
                'id': row['id'],
            },
        )

    subject_rows = conn.execute(sa.text('SELECT id, created_at FROM subjects')).mappings().all()
    for row in subject_rows:
        conn.execute(
            sa.text(
                'UPDATE subjects '
                'SET uuid = :uuid, '
                'updated_at = COALESCE(updated_at, :created_at, CURRENT_TIMESTAMP), '
                'is_deleted = COALESCE(is_deleted, 0) '
                'WHERE id = :id'
            ),
            {
                'uuid': str(uuid4()),
                'created_at': row['created_at'],
                'id': row['id'],
            },
        )

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_users_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_users_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('subjects') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_subjects_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_subjects_is_deleted', ['is_deleted'], unique=False)


def downgrade():
    with op.batch_alter_table('subjects') as batch_op:
        batch_op.drop_index('ix_subjects_is_deleted')
        batch_op.drop_index('ix_subjects_uuid')

    op.drop_column('subjects', 'deleted_at')
    op.drop_column('subjects', 'is_deleted')
    op.drop_column('subjects', 'updated_at')
    op.drop_column('subjects', 'uuid')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index('ix_users_is_deleted')
        batch_op.drop_index('ix_users_uuid')

    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'is_deleted')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'uuid')
