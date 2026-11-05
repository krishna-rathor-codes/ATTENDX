import csv
import io
import json
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
from sqlalchemy.orm import Session

from app.models import AuditLog, AttendanceSession, Class, Enrollment, Role, User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Normalize database datetimes so SQLite and PostgreSQL behave consistently."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def new_qr_token() -> str:
    return secrets.token_urlsafe(32)


def audit(db: Session, actor_id: int | None, action: str, entity_type: str, entity_id: int | str | None = None, details: dict | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None, details=json.dumps(details) if details else None))


def teacher_class_or_404(db: Session, class_id: int, teacher_id: int) -> Class:
    class_ref = db.get(Class, class_id)
    if not class_ref or class_ref.teacher_id != teacher_id:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_ref


def ensure_student_enrolled(db: Session, class_id: int, student_id: int) -> Enrollment:
    enrollment = db.query(Enrollment).filter_by(class_id=class_id, student_id=student_id).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail="Student is not enrolled in this class")
    return enrollment


def attendance_csv(rows: list[dict]) -> io.BytesIO:
    output = io.StringIO()
    fields = ["student_name", "student_email", "class_name", "subject_name", "status", "source", "marked_at", "note"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows({key: row.get(key, "") for key in fields} for row in rows)
    return io.BytesIO(output.getvalue().encode("utf-8"))


def attendance_pdf(rows: list[dict]) -> io.BytesIO:
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, rightMargin=32, leftMargin=32, topMargin=32, bottomMargin=32)
    styles = getSampleStyleSheet()
    story = [Paragraph("AttendX Attendance Report", styles["Title"]), Spacer(1, 12)]
    table_data = [["Student", "Class", "Subject", "Status", "Source", "Marked at"]]
    table_data.extend([[row["student_name"], row["class_name"], row["subject_name"], row["status"], row["source"], row["marked_at"]] for row in rows])
    table = Table(table_data, repeatRows=1, colWidths=[100, 80, 90, 55, 48, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#155e75")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    doc.build(story)
    output.seek(0)
    return output
