import os
import firebase_admin
from firebase_admin import credentials, auth
from app.core.config import get_settings

_initialized = False


def init_firebase():
    global _initialized
    if _initialized:
        return

    settings = get_settings()

    service_account_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "firebase-service-account.json",
    )

    if os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
    elif settings.FIREBASE_PROJECT_ID:
        firebase_admin.initialize_app(options={
            "projectId": settings.FIREBASE_PROJECT_ID,
        })

    _initialized = True


def verify_firebase_token(id_token: str):
    """Verify a Firebase ID token and return the decoded token."""
    init_firebase()
    return auth.verify_id_token(id_token)
