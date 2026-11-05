from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession
from app.models import Role, User
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.security import create_access_token, hash_password, verify_password
from app.utils import audit

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    if payload.role == Role.STUDENT.value and not payload.student_id:
        raise HTTPException(status_code=422, detail="Student ID is required for student accounts")
    user = User(full_name=payload.full_name, email=email, password_hash=hash_password(payload.password), role=payload.role, student_id=payload.student_id)
    db.add(user)
    try:
        db.flush()
        audit(db, user.id, "registered", "user", user.id, {"role": user.role})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Student ID is already in use")
    db.refresh(user)
    return AuthResponse(access_token=create_access_token(user.id, user.role), user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: DbSession):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive")
    audit(db, user.id, "logged_in", "user", user.id)
    db.commit()
    return AuthResponse(access_token=create_access_token(user.id, user.role), user=user)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser):
    return user
