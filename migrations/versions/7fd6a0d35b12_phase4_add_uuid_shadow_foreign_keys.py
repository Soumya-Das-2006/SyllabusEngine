"""phase4_add_uuid_shadow_foreign_keys

Revision ID: 7fd6a0d35b12
Revises: b0d57f78f74f
Create Date: 2026-03-29 14:26:30.258539

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7fd6a0d35b12'
down_revision = 'b0d57f78f74f'
branch_labels = None
depends_on = None


def upgrade():
    shadow_columns = {
        'subjects': ['user_uuid'],
        'syllabi': ['subject_uuid'],
        'study_plans': ['subject_uuid'],
        'assignments': ['subject_uuid'],
        'calendar_events': ['user_uuid', 'subject_uuid'],
        'progress': ['user_uuid', 'subject_uuid'],
        'ai_conversations': ['user_uuid', 'subject_uuid'],
        'oauth_tokens': ['user_uuid'],
        'quizzes': ['user_uuid', 'subject_uuid'],
        'questions': ['quiz_uuid'],
        'user_quiz_attempts': ['user_uuid', 'quiz_uuid', 'subject_uuid'],
        'topic_performance': ['user_uuid', 'subject_uuid'],
        'study_analytics': ['user_uuid', 'subject_uuid'],
        'study_schedules': ['user_uuid', 'subject_uuid'],
        'notes': ['user_uuid', 'subject_uuid'],
        'chat_rooms': ['subject_uuid', 'created_by_uuid'],
        'chat_messages': ['room_uuid', 'user_uuid'],
        'notifications': ['user_uuid'],
        'activity_logs': ['user_uuid'],
        'certificates': ['user_uuid', 'quiz_uuid'],
        'attendance_sessions': ['subject_uuid', 'created_by_uuid'],
        'attendance_records': ['session_uuid', 'user_uuid'],
    }

    for table_name, columns in shadow_columns.items():
        for column_name in columns:
            op.add_column(table_name, sa.Column(column_name, sa.String(length=36), nullable=True))
            op.create_index(f'ix_{table_name}_{column_name}', table_name, [column_name], unique=False)

    conn = op.get_bind()
    backfill_sql = [
        "UPDATE subjects SET user_uuid = (SELECT uuid FROM users WHERE users.id = subjects.user_id) WHERE user_id IS NOT NULL",
        "UPDATE syllabi SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = syllabi.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE study_plans SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = study_plans.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE assignments SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = assignments.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE calendar_events SET user_uuid = (SELECT uuid FROM users WHERE users.id = calendar_events.user_id) WHERE user_id IS NOT NULL",
        "UPDATE calendar_events SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = calendar_events.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE progress SET user_uuid = (SELECT uuid FROM users WHERE users.id = progress.user_id) WHERE user_id IS NOT NULL",
        "UPDATE progress SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = progress.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE ai_conversations SET user_uuid = (SELECT uuid FROM users WHERE users.id = ai_conversations.user_id) WHERE user_id IS NOT NULL",
        "UPDATE ai_conversations SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = ai_conversations.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE oauth_tokens SET user_uuid = (SELECT uuid FROM users WHERE users.id = oauth_tokens.user_id) WHERE user_id IS NOT NULL",
        "UPDATE quizzes SET user_uuid = (SELECT uuid FROM users WHERE users.id = quizzes.user_id) WHERE user_id IS NOT NULL",
        "UPDATE quizzes SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = quizzes.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE questions SET quiz_uuid = (SELECT uuid FROM quizzes WHERE quizzes.id = questions.quiz_id) WHERE quiz_id IS NOT NULL",
        "UPDATE user_quiz_attempts SET user_uuid = (SELECT uuid FROM users WHERE users.id = user_quiz_attempts.user_id) WHERE user_id IS NOT NULL",
        "UPDATE user_quiz_attempts SET quiz_uuid = (SELECT uuid FROM quizzes WHERE quizzes.id = user_quiz_attempts.quiz_id) WHERE quiz_id IS NOT NULL",
        "UPDATE user_quiz_attempts SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = user_quiz_attempts.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE topic_performance SET user_uuid = (SELECT uuid FROM users WHERE users.id = topic_performance.user_id) WHERE user_id IS NOT NULL",
        "UPDATE topic_performance SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = topic_performance.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE study_analytics SET user_uuid = (SELECT uuid FROM users WHERE users.id = study_analytics.user_id) WHERE user_id IS NOT NULL",
        "UPDATE study_analytics SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = study_analytics.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE study_schedules SET user_uuid = (SELECT uuid FROM users WHERE users.id = study_schedules.user_id) WHERE user_id IS NOT NULL",
        "UPDATE study_schedules SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = study_schedules.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE notes SET user_uuid = (SELECT uuid FROM users WHERE users.id = notes.user_id) WHERE user_id IS NOT NULL",
        "UPDATE notes SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = notes.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE chat_rooms SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = chat_rooms.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE chat_rooms SET created_by_uuid = (SELECT uuid FROM users WHERE users.id = chat_rooms.created_by) WHERE created_by IS NOT NULL",
        "UPDATE chat_messages SET room_uuid = (SELECT uuid FROM chat_rooms WHERE chat_rooms.id = chat_messages.room_id) WHERE room_id IS NOT NULL",
        "UPDATE chat_messages SET user_uuid = (SELECT uuid FROM users WHERE users.id = chat_messages.user_id) WHERE user_id IS NOT NULL",
        "UPDATE notifications SET user_uuid = (SELECT uuid FROM users WHERE users.id = notifications.user_id) WHERE user_id IS NOT NULL",
        "UPDATE activity_logs SET user_uuid = (SELECT uuid FROM users WHERE users.id = activity_logs.user_id) WHERE user_id IS NOT NULL",
        "UPDATE certificates SET user_uuid = (SELECT uuid FROM users WHERE users.id = certificates.user_id) WHERE user_id IS NOT NULL",
        "UPDATE certificates SET quiz_uuid = (SELECT uuid FROM quizzes WHERE quizzes.id = certificates.quiz_id) WHERE quiz_id IS NOT NULL",
        "UPDATE attendance_sessions SET subject_uuid = (SELECT uuid FROM subjects WHERE subjects.id = attendance_sessions.subject_id) WHERE subject_id IS NOT NULL",
        "UPDATE attendance_sessions SET created_by_uuid = (SELECT uuid FROM users WHERE users.id = attendance_sessions.created_by) WHERE created_by IS NOT NULL",
        "UPDATE attendance_records SET session_uuid = (SELECT uuid FROM attendance_sessions WHERE attendance_sessions.id = attendance_records.session_id) WHERE session_id IS NOT NULL",
        "UPDATE attendance_records SET user_uuid = (SELECT uuid FROM users WHERE users.id = attendance_records.user_id) WHERE user_id IS NOT NULL",
    ]
    for statement in backfill_sql:
        conn.execute(sa.text(statement))


def downgrade():
    shadow_columns = {
        'attendance_records': ['session_uuid', 'user_uuid'],
        'attendance_sessions': ['subject_uuid', 'created_by_uuid'],
        'certificates': ['user_uuid', 'quiz_uuid'],
        'activity_logs': ['user_uuid'],
        'notifications': ['user_uuid'],
        'chat_messages': ['room_uuid', 'user_uuid'],
        'chat_rooms': ['subject_uuid', 'created_by_uuid'],
        'notes': ['user_uuid', 'subject_uuid'],
        'study_schedules': ['user_uuid', 'subject_uuid'],
        'study_analytics': ['user_uuid', 'subject_uuid'],
        'topic_performance': ['user_uuid', 'subject_uuid'],
        'user_quiz_attempts': ['user_uuid', 'quiz_uuid', 'subject_uuid'],
        'questions': ['quiz_uuid'],
        'quizzes': ['user_uuid', 'subject_uuid'],
        'oauth_tokens': ['user_uuid'],
        'ai_conversations': ['user_uuid', 'subject_uuid'],
        'progress': ['user_uuid', 'subject_uuid'],
        'calendar_events': ['user_uuid', 'subject_uuid'],
        'assignments': ['subject_uuid'],
        'study_plans': ['subject_uuid'],
        'syllabi': ['subject_uuid'],
        'subjects': ['user_uuid'],
    }

    for table_name, columns in shadow_columns.items():
        for column_name in columns:
            op.drop_index(f'ix_{table_name}_{column_name}', table_name=table_name)
            op.drop_column(table_name, column_name)
