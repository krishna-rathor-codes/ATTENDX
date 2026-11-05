from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func

from app.core.config import settings
from app.dependencies import CurrentUser, DbSession
from app.models import AttendanceRecord, AttendanceSession, AttendanceStatus, AuditLog, Class, Enrollment, Role, Subject, User, utcnow
from app.schemas import AttendanceRecordResponse, AttendanceSummary, AuditResponse, ClassCreate, ClassResponse, EnrollRequest, ManualAttendanceRequest, SessionResponse, StudentBrief, SubjectCreate, SubjectResponse
from app.utils import attendance_csv, attendance_pdf, audit, ensure_student_enrolled, new_qr_token, teacher_class_or_404

router = APIRouter(prefix="/teacher", tags=["teacher"])


def teacher_only(user: CurrentUser):
    if user.role != Role.TEACHER.value:
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user


@router.get("/subjects", response_model=list[SubjectResponse])
def list_subjects(user: CurrentUser, db: DbSession):
    teacher_only(user)
    return db.query(Subject).order_by(Subject.name).all()


@router.post("/subjects", response_model=SubjectResponse, status_code=201)
def create_subject(payload: SubjectCreate, user: CurrentUser, db: DbSession):
    teacher_only(user)
    code = payload.code.strip().upper()
    if db.query(Subject).filter(Subject.code == code).first():
        raise HTTPException(status_code=409, detail="Subject code already exists")
    subject = Subject(code=code, name=payload.name.strip(), description=payload.description)
    db.add(subject)
    db.flush()
    audit(db, user.id, "created", "subject", subject.id, {"code": code})
    db.commit()
    db.refresh(subject)
    return subject


@router.get("/classes", response_model=list[ClassResponse])
def list_classes(user: CurrentUser, db: DbSession):
    teacher_only(user)
    classes = db.query(Class, Subject).join(Subject, Class.subject_id == Subject.id).filter(Class.teacher_id == user.id).order_by(Class.name).all()
    result = []
    now = utcnow()
    for class_ref, subject in classes:
        active = db.query(AttendanceSession).filter(AttendanceSession.class_id == class_ref.id, AttendanceSession.closed_at.is_(None), AttendanceSession.expires_at > now).order_by(AttendanceSession.id.desc()).first()
        result.append(ClassResponse(id=class_ref.id, name=class_ref.name, section=class_ref.section, subject_id=subject.id, subject_code=subject.code, subject_name=subject.name, enrolled_count=db.query(func.count(Enrollment.id)).filter(Enrollment.class_id == class_ref.id).scalar() or 0, active_session_id=active.id if active else None))
    return result


@router.post("/classes", response_model=ClassResponse, status_code=201)
def create_class(payload: ClassCreate, user: CurrentUser, db: DbSession):
    teacher_only(user)
    subject = db.get(Subject, payload.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    class_ref = Class(name=payload.name.strip(), section=payload.section.strip(), subject_id=subject.id, teacher_id=user.id)
    db.add(class_ref)
    db.flush()
    audit(db, user.id, "created", "class", class_ref.id, {"name": class_ref.name})
    db.commit()
    return ClassResponse(id=class_ref.id, name=class_ref.name, section=class_ref.section, subject_id=subject.id, subject_code=subject.code, subject_name=subject.name, enrolled_count=0)


@router.get("/classes/{class_id}/students", response_model=list[StudentBrief])
def list_students(class_id: int, user: CurrentUser, db: DbSession):
    teacher_class_or_404(db, class_id, teacher_only(user).id)
    return db.query(User).join(Enrollment, Enrollment.student_id == User.id).filter(Enrollment.class_id == class_id).order_by(User.full_name).all()


@router.post("/classes/{class_id}/students", response_model=StudentBrief, status_code=201)
def enroll_student(class_id: int, payload: EnrollRequest, user: CurrentUser, db: DbSession):
    teacher_class_or_404(db, class_id, teacher_only(user).id)
    student = db.query(User).filter(User.email == payload.email.lower(), User.role == Role.STUDENT.value).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student account not found")
    if db.query(Enrollment).filter_by(class_id=class_id, student_id=student.id).first():
        raise HTTPException(status_code=409, detail="Student is already enrolled")
    db.add(Enrollment(class_id=class_id, student_id=student.id))
    audit(db, user.id, "enrolled", "student", student.id, {"class_id": class_id})
    db.commit()
    return student


@router.post("/classes/{class_id}/sessions", response_model=SessionResponse, status_code=201)
def create_session(class_id: int, user: CurrentUser, db: DbSession):
    teacher_class_or_404(db, class_id, teacher_only(user).id)
    class_ref = db.get(Class, class_id)
    now = utcnow()
    db.query(AttendanceSession).filter(AttendanceSession.class_id == class_id, AttendanceSession.closed_at.is_(None), AttendanceSession.expires_at > now).update({AttendanceSession.closed_at: now})
    session = AttendanceSession(class_id=class_id, created_by=user.id, token=new_qr_token(), starts_at=now, expires_at=now + timedelta(minutes=settings.qr_session_minutes))
    db.add(session)
    db.flush()
    audit(db, user.id, "created", "attendance_session", session.id, {"class_id": class_id})
    db.commit()
    db.refresh(session)
    return session_response(session)


@router.post("/sessions/{session_id}/close", response_model=SessionResponse)
def close_session(session_id: int, user: CurrentUser, db: DbSession):
    session = db.get(AttendanceSession, session_id)
    if not session or session.class_ref.teacher_id != teacher_only(user).id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.closed_at = utcnow()
    audit(db, user.id, "closed", "attendance_session", session.id)
    db.commit()
    return session_response(session)


@router.get("/sessions/{session_id}/records", response_model=list[AttendanceRecordResponse])
def session_records(session_id: int, user: CurrentUser, db: DbSession):
    session = db.get(AttendanceSession, session_id)
    if not session or session.class_ref.teacher_id != teacher_only(user).id:
        raise HTTPException(status_code=404, detail="Session not found")
    return records_for_query(db, session_id=session_id)


@router.put("/sessions/{session_id}/records", response_model=AttendanceRecordResponse)
def manual_attendance(session_id: int, payload: ManualAttendanceRequest, user: CurrentUser, db: DbSession):
    session = db.get(AttendanceSession, session_id)
    teacher_only(user)
    if not session or session.class_ref.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    ensure_student_enrolled(db, session.class_id, payload.student_id)
    record = db.query(AttendanceRecord).filter_by(session_id=session_id, student_id=payload.student_id).first()
    if record:
        record.status = payload.status
        record.source = "manual"
        record.note = payload.note
        record.marked_at = utcnow()
    else:
        record = AttendanceRecord(session_id=session_id, student_id=payload.student_id, status=payload.status, source="manual", note=payload.note)
        db.add(record)
    audit(db, user.id, "updated", "attendance_record", record.id, {"status": payload.status, "source": "manual"})
    db.commit()
    return records_for_query(db, session_id=session_id, student_id=payload.student_id)[0]


@router.get("/summaries", response_model=list[AttendanceSummary])
def teacher_summaries(user: CurrentUser, db: DbSession):
    teacher_only(user)
    return summaries_for_teacher(db, user.id)


@router.get("/audit", response_model=list[AuditResponse])
def audit_logs(user: CurrentUser, db: DbSession, limit: int = 100):
    teacher_only(user)
    logs = db.query(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.actor_id).filter((AuditLog.actor_id == user.id) | (AuditLog.entity_type.in_(["attendance_record", "attendance_session"]))).order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).all()
    return [AuditResponse(id=log.id, action=log.action, entity_type=log.entity_type, entity_id=log.entity_id, details=log.details, created_at=log.created_at, actor_name=name) for log, name in logs]


@router.get("/reports/{file_type}")
def report(file_type: Literal["csv", "pdf"], user: CurrentUser, db: DbSession, class_id: int | None = None):
    teacher_only(user)
    query = db.query(AttendanceRecord).join(AttendanceSession).join(Class).filter(Class.teacher_id == user.id)
    if class_id is not None:
        query = query.filter(AttendanceSession.class_id == class_id)
    rows = [record_dict(row) for row in query.order_by(AttendanceRecord.marked_at.desc()).all()]
    if file_type == "csv":
        return StreamingResponse(attendance_csv(rows), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=attendx-attendance.csv"})
    return StreamingResponse(attendance_pdf(rows), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=attendx-attendance.pdf"})


def session_response(session: AttendanceSession) -> SessionResponse:
    return SessionResponse(id=session.id, class_id=session.class_id, class_name=session.class_ref.name, subject_name=session.class_ref.subject.name, token=session.token, qr_payload=f"attendx://attendance?session_id={session.id}&token={session.token}", starts_at=session.starts_at, expires_at=session.expires_at, closed_at=session.closed_at, marked_count=len(session.records))


def record_dict(record: AttendanceRecord) -> dict:
    return {"student_name": record.student.full_name, "student_email": record.student.email, "class_name": record.session.class_ref.name, "subject_name": record.session.class_ref.subject.name, "status": record.status, "source": record.source, "marked_at": record.marked_at.isoformat(), "note": record.note}


def records_for_query(db: DbSession, session_id: int | None = None, student_id: int | None = None) -> list[AttendanceRecordResponse]:
    query = db.query(AttendanceRecord).join(AttendanceSession).join(Class).join(Subject).join(User, User.id == AttendanceRecord.student_id)
    if session_id is not None:
        query = query.filter(AttendanceRecord.session_id == session_id)
    if student_id is not None:
        query = query.filter(AttendanceRecord.student_id == student_id)
    rows = query.order_by(AttendanceRecord.marked_at.desc()).all()
    return [AttendanceRecordResponse(id=r.id, session_id=r.session_id, class_id=r.session.class_id, class_name=r.session.class_ref.name, subject_name=r.session.class_ref.subject.name, student_id=r.student_id, student_name=r.student.full_name, student_email=r.student.email, status=r.status, source=r.source, marked_at=r.marked_at, note=r.note) for r in rows]


def summaries_for_teacher(db: DbSession, teacher_id: int) -> list[AttendanceSummary]:
    classes = db.query(Class).filter(Class.teacher_id == teacher_id).order_by(Class.name).all()
    result = []
    for class_ref in classes:
        total = db.query(func.count(AttendanceSession.id)).filter(AttendanceSession.class_id == class_ref.id).scalar() or 0
        present = db.query(func.count(AttendanceRecord.id)).join(AttendanceSession).filter(AttendanceSession.class_id == class_ref.id, AttendanceRecord.status == AttendanceStatus.PRESENT.value).scalar() or 0
        late = db.query(func.count(AttendanceRecord.id)).join(AttendanceSession).filter(AttendanceSession.class_id == class_ref.id, AttendanceRecord.status == AttendanceStatus.LATE.value).scalar() or 0
        enrolled = db.query(func.count(Enrollment.id)).filter(Enrollment.class_id == class_ref.id).scalar() or 0
        denominator = total * enrolled
        absent = max(denominator - present - late, 0)
        percentage = round(((present + late) / denominator) * 100, 1) if denominator else 0.0
        result.append(AttendanceSummary(class_id=class_ref.id, class_name=class_ref.name, subject_name=class_ref.subject.name, total_sessions=total, present_count=present, late_count=late, absent_count=absent, percentage=percentage, below_threshold=percentage < 75))
    return result
