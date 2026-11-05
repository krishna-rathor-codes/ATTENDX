from fastapi import APIRouter, HTTPException
from sqlalchemy import func

from app.dependencies import CurrentUser, DbSession
from app.models import AttendanceRecord, AttendanceSession, AttendanceStatus, Class, Enrollment, Role, Subject, User, utcnow
from app.routers.teacher import records_for_query
from app.schemas import AttendanceRecordResponse, AttendanceSummary, ScanRequest
from app.utils import as_utc, audit, ensure_student_enrolled

router = APIRouter(prefix="/student", tags=["student"])


def student_only(user: CurrentUser):
    if user.role != Role.STUDENT.value:
        raise HTTPException(status_code=403, detail="Student access required")
    return user


@router.get("/summaries", response_model=list[AttendanceSummary])
def student_summaries(user: CurrentUser, db: DbSession):
    student_only(user)
    enrollments = db.query(Enrollment).join(Class).filter(Enrollment.student_id == user.id).order_by(Class.name).all()
    result = []
    for enrollment in enrollments:
        class_ref = enrollment.class_ref
        total = db.query(func.count(AttendanceSession.id)).filter(AttendanceSession.class_id == class_ref.id).scalar() or 0
        present = db.query(func.count(AttendanceRecord.id)).join(AttendanceSession).filter(AttendanceSession.class_id == class_ref.id, AttendanceRecord.student_id == user.id, AttendanceRecord.status == AttendanceStatus.PRESENT.value).scalar() or 0
        late = db.query(func.count(AttendanceRecord.id)).join(AttendanceSession).filter(AttendanceSession.class_id == class_ref.id, AttendanceRecord.student_id == user.id, AttendanceRecord.status == AttendanceStatus.LATE.value).scalar() or 0
        absent = max(total - present - late, 0)
        percentage = round(((present + late) / total) * 100, 1) if total else 0.0
        result.append(AttendanceSummary(class_id=class_ref.id, class_name=class_ref.name, subject_name=class_ref.subject.name, total_sessions=total, present_count=present, late_count=late, absent_count=absent, percentage=percentage, below_threshold=percentage < 75))
    return result


@router.get("/history", response_model=list[AttendanceRecordResponse])
def student_history(user: CurrentUser, db: DbSession):
    student_only(user)
    return records_for_query(db, student_id=user.id)


@router.post("/scan", response_model=AttendanceRecordResponse)
def scan_attendance(payload: ScanRequest, user: CurrentUser, db: DbSession):
    student_only(user)
    session = db.get(AttendanceSession, payload.session_id)
    now = utcnow()
    if not session or session.token != payload.token:
        raise HTTPException(status_code=400, detail="This attendance QR is not valid")
    if session.closed_at or as_utc(session.expires_at) <= now:
        raise HTTPException(status_code=410, detail="This attendance QR has expired")
    ensure_student_enrolled(db, session.class_id, user.id)
    existing = db.query(AttendanceRecord).filter_by(session_id=session.id, student_id=user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Attendance has already been recorded for this session")
    record = AttendanceRecord(session_id=session.id, student_id=user.id, status=AttendanceStatus.PRESENT.value, source="qr")
    db.add(record)
    db.flush()
    audit(db, user.id, "scanned", "attendance_record", record.id, {"session_id": session.id})
    db.commit()
    return records_for_query(db, session_id=session.id, student_id=user.id)[0]
