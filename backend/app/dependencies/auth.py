import logging

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.firebase import verify_firebase_token
from app.database.base import get_db
from app.models.user import User

logger = logging.getLogger("app.auth")

security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        logger.warning("Authentication failed: missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )
    token = credentials.credentials

    try:
        decoded_token = verify_firebase_token(token)
    except Exception:
        logger.warning("Authentication failed: invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase token",
        )

    firebase_uid = decoded_token["uid"]

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if user:
        # Local user already exists: the normal authenticated-request path is
        # read-only. The user row is returned without any mutation or commit, so
        # no SELECT-side INSERT/UPDATE/DELETE is emitted. Firebase identity
        # fields (email/name/picture) are NOT re-synchronized here; explicit
        # profile updates own intentional changes. This avoids an UPDATE (and an
        # updated_at bump) on every authenticated request.
        return user

    # First-login provisioning (intentional write): create the local user from
    # the verified token's identity claims. This only runs when no local user
    # exists yet.
    email = decoded_token.get("email", "")
    name = decoded_token.get("name", "")
    profile_picture_url = decoded_token.get("picture")

    user = User(
        firebase_uid=firebase_uid,
        email=email,
        name=name,
        profile_picture_url=profile_picture_url,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent first-login already created this Firebase UID; the unique
        # constraint on users.firebase_uid rejected our INSERT. Roll back this
        # transaction and return the existing winner rather than erroring or
        # creating a duplicate.
        db.rollback()
        existing = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if existing is not None:
            return existing
        raise
    db.refresh(user)
    return user
