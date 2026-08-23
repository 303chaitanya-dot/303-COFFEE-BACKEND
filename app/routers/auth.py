from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user, hash_password, require_owner, verify_password
from app.db import get_db
from app.models import User
from app.presenters import present_user
from app.schemas import LoginIn, PasswordIn, ProfileIn, TokenOut, UserCreateIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return TokenOut(access_token=create_token(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return present_user(user)


@router.put("/me", response_model=UserOut)
def update_me(payload: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    user.name = payload.name
    user.phone = payload.phone
    user.title = payload.title
    db.commit()
    db.refresh(user)
    return present_user(user)


@router.post("/me/password")
def change_password(payload: PasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is wrong")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"status": "ok"}


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_owner)) -> list[UserOut]:
    rows = db.scalars(select(User).order_by(User.name)).all()
    return [present_user(row) for row in rows]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreateIn, db: Session = Depends(get_db), _: User = Depends(require_owner)) -> UserOut:
    email = payload.email.strip().lower()
    if payload.role not in {"owner", "manager", "staff"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="A profile with that email already exists")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        phone=payload.phone,
        title=payload.title,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return present_user(user)
