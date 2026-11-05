import os

os.environ["DATABASE_URL"] = "sqlite:///./test_attendx.db"
os.environ["SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def register(email: str, role: str, student_id: str | None = None):
    return client.post("/api/auth/register", json={"full_name": email.split("@")[0], "email": email, "password": "Password@123", "role": role, "student_id": student_id})


def test_localhost_alias_is_allowed_by_cors():
    response = client.options("/api/auth/register", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_registration_and_login():
    response = register("teacher@example.com", "teacher")
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"email": "teacher@example.com", "password": "Password@123"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "teacher"


def test_qr_flow_and_duplicate_prevention():
    teacher_response = register("owner@example.com", "teacher")
    student_response = register("learner@example.com", "student", "STU-TEST")
    teacher_token = teacher_response.json()["access_token"]
    student_token = student_response.json()["access_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}
    subject = client.post("/api/teacher/subjects", headers=teacher_headers, json={"code": "MAT101", "name": "Mathematics"})
    class_response = client.post("/api/teacher/classes", headers=teacher_headers, json={"name": "Year 1", "section": "A", "subject_id": subject.json()["id"]})
    class_id = class_response.json()["id"]
    assert client.post(f"/api/teacher/classes/{class_id}/students", headers=teacher_headers, json={"email": "learner@example.com"}).status_code == 201
    session = client.post(f"/api/teacher/classes/{class_id}/sessions", headers=teacher_headers)
    assert session.status_code == 201
    payload = session.json()
    scan = client.post("/api/student/scan", headers=student_headers, json={"session_id": payload["id"], "token": payload["token"]})
    assert scan.status_code == 200
    duplicate = client.post("/api/student/scan", headers=student_headers, json={"session_id": payload["id"], "token": payload["token"]})
    assert duplicate.status_code == 409
