from app.db import Base, SessionLocal, engine
from app.models import Class, Enrollment, Subject, User
from app.security import hash_password


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        teacher = db.query(User).filter_by(email="teacher@attendx.local").first()
        if not teacher:
            teacher = User(full_name="Maya Sharma", email="teacher@attendx.local", password_hash=hash_password("Teacher@123"), role="teacher")
            db.add(teacher)
        student = db.query(User).filter_by(email="student@attendx.local").first()
        if not student:
            student = User(full_name="Arjun Mehta", email="student@attendx.local", password_hash=hash_password("Student@123"), role="student", student_id="STU-001")
            db.add(student)
        db.flush()
        subject = db.query(Subject).filter_by(code="CS101").first()
        if not subject:
            subject = Subject(code="CS101", name="Computer Science", description="Foundations of computing")
            db.add(subject)
            db.flush()
        class_ref = db.query(Class).filter_by(name="B.Tech CSE", teacher_id=teacher.id).first()
        if not class_ref:
            class_ref = Class(name="B.Tech CSE", section="A", teacher_id=teacher.id, subject_id=subject.id)
            db.add(class_ref)
            db.flush()
        if not db.query(Enrollment).filter_by(class_id=class_ref.id, student_id=student.id).first():
            db.add(Enrollment(class_id=class_ref.id, student_id=student.id))
        db.commit()
        print("Seed complete: teacher@attendx.local / Teacher@123; student@attendx.local / Student@123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
