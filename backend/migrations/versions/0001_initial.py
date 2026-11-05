"""create AttendX tables"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("full_name", sa.String(120), nullable=False), sa.Column("email", sa.String(255), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(20), nullable=False), sa.Column("student_id", sa.String(50)), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("subjects", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(30), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_subjects_code", "subjects", ["code"], unique=True)
    op.create_table("classes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("section", sa.String(40), nullable=False), sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("enrollments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False), sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("class_id", "student_id", name="uq_class_student"))
    op.create_table("attendance_sessions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False), sa.Column("token", sa.String(128), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("closed_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("token"))
    op.create_index("ix_attendance_sessions_token", "attendance_sessions", ["token"], unique=True)
    op.create_table("attendance_records", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("attendance_sessions.id"), nullable=False), sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("source", sa.String(20), nullable=False), sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False), sa.Column("note", sa.String(255)), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("session_id", "student_id", name="uq_session_student"))
    op.create_table("audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("action", sa.String(80), nullable=False), sa.Column("entity_type", sa.String(50), nullable=False), sa.Column("entity_id", sa.String(50)), sa.Column("details", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("attendance_records")
    op.drop_index("ix_attendance_sessions_token", table_name="attendance_sessions")
    op.drop_table("attendance_sessions")
    op.drop_table("enrollments")
    op.drop_table("classes")
    op.drop_index("ix_subjects_code", table_name="subjects")
    op.drop_table("subjects")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
