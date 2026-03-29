"""phase2_uuid_audit_quiz_note_certificate

Revision ID: cf6b6076f44b
Revises: 5496ce7a44d9
Create Date: 2026-03-29 12:52:53.202815

"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4


# revision identifiers, used by Alembic.
revision = 'cf6b6076f44b'
down_revision = '5496ce7a44d9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('quizzes', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('quizzes', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('quizzes', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('quizzes', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('notes', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('notes', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('notes', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    op.add_column('certificates', sa.Column('uuid', sa.String(length=36), nullable=True))
    op.add_column('certificates', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('certificates', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('certificates', sa.Column('is_deleted', sa.Boolean(), nullable=True))
    op.add_column('certificates', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    conn = op.get_bind()

    quiz_rows = conn.execute(sa.text('SELECT id, created_at FROM quizzes')).mappings().all()
    for row in quiz_rows:
        conn.execute(
            sa.text(
                'UPDATE quizzes '
                'SET uuid = :uuid, '
                'updated_at = COALESCE(updated_at, :created_at, CURRENT_TIMESTAMP), '
                'is_deleted = COALESCE(is_deleted, 0) '
                'WHERE id = :id'
            ),
            {'uuid': str(uuid4()), 'created_at': row['created_at'], 'id': row['id']},
        )

    note_rows = conn.execute(sa.text('SELECT id FROM notes')).mappings().all()
    for row in note_rows:
        conn.execute(
            sa.text(
                'UPDATE notes '
                'SET uuid = :uuid, '
                'is_deleted = COALESCE(is_deleted, 0) '
                'WHERE id = :id'
            ),
            {'uuid': str(uuid4()), 'id': row['id']},
        )

    cert_rows = conn.execute(sa.text('SELECT id, issued_at FROM certificates')).mappings().all()
    for row in cert_rows:
        conn.execute(
            sa.text(
                'UPDATE certificates '
                'SET uuid = :uuid, '
                'created_at = COALESCE(created_at, :issued_at, CURRENT_TIMESTAMP), '
                'updated_at = COALESCE(updated_at, :issued_at, CURRENT_TIMESTAMP), '
                'is_deleted = COALESCE(is_deleted, 0) '
                'WHERE id = :id'
            ),
            {'uuid': str(uuid4()), 'issued_at': row['issued_at'], 'id': row['id']},
        )

    with op.batch_alter_table('quizzes') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_quizzes_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_quizzes_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('notes') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_notes_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_notes_is_deleted', ['is_deleted'], unique=False)

    with op.batch_alter_table('certificates') as batch_op:
        batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column('is_deleted', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index('ix_certificates_uuid', ['uuid'], unique=True)
        batch_op.create_index('ix_certificates_is_deleted', ['is_deleted'], unique=False)


def downgrade():
    with op.batch_alter_table('certificates') as batch_op:
        batch_op.drop_index('ix_certificates_is_deleted')
        batch_op.drop_index('ix_certificates_uuid')

    op.drop_column('certificates', 'deleted_at')
    op.drop_column('certificates', 'is_deleted')
    op.drop_column('certificates', 'updated_at')
    op.drop_column('certificates', 'created_at')
    op.drop_column('certificates', 'uuid')

    with op.batch_alter_table('notes') as batch_op:
        batch_op.drop_index('ix_notes_is_deleted')
        batch_op.drop_index('ix_notes_uuid')

    op.drop_column('notes', 'deleted_at')
    op.drop_column('notes', 'is_deleted')
    op.drop_column('notes', 'uuid')

    with op.batch_alter_table('quizzes') as batch_op:
        batch_op.drop_index('ix_quizzes_is_deleted')
        batch_op.drop_index('ix_quizzes_uuid')

    op.drop_column('quizzes', 'deleted_at')
    op.drop_column('quizzes', 'is_deleted')
    op.drop_column('quizzes', 'updated_at')
    op.drop_column('quizzes', 'uuid')
