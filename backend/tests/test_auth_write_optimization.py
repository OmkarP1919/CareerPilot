"""Phase 5E.8 - authentication per-request write optimization tests.

Exercises the REAL ``get_current_user`` dependency (no dependency override of the
auth path) against an in-memory database, patching only Firebase token
verification. Proves the normal authenticated-request path is read-only:

- existing local user  -> authentication SELECT only, zero INSERT/UPDATE/DELETE
- first login          -> exactly one INSERT (provisioning), no stray UPDATE
- duplicate/parallel first login -> unique constraint prevents duplicates, the
  race loser recovers and returns the existing winner

Also verifies authorization isolation, token-clean logging, and that an explicit
profile update still performs its own intended write.
"""
import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.dependencies import auth as auth_module
from app.dependencies.auth import get_current_user
from app.database.base import Base, get_db
from app.models.user import User


class _WriteCounter:
    """Counts executed SQL statements per kind via engine event listener."""

    def __init__(self, engine):
        self.engine = engine
        self.statements = []
        event.listen(engine, "before_cursor_execute", self._capture)

    def _capture(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement.strip().lstrip("(").upper())

    def reset(self):
        self.statements = []

    def _kinds(self):
        kinds = {"INSERT": 0, "UPDATE": 0, "DELETE": 0, "SELECT": 0}
        for stmt in self.statements:
            for kw in kinds:
                if stmt.startswith(kw):
                    kinds[kw] += 1
                    break
        return kinds

    @property
    def w_kinds(self):
        return {k: v for k, v in self._kinds().items() if k != "SELECT"}

    def select_count(self):
        return self._kinds()["SELECT"]


def _session_overrider(Session):
    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()
    return override_get_db


class AuthHarnessMixin:
    USER_A = {"id": "user_a", "firebase_uid": "fb_a", "email": "a@test.com",
              "name": "User A", "picture": "http://x/a.png"}

    def _make_engine(self, users):
        """Create a file-backed temp DB with the given Users; return (engine, Session).

        A file-backed SQLite DB (rather than in-memory) is used so the table
        is visible to the TestClient/ASGI worker threads, which use separate
        connections from the setup thread.
        """
        self._tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self._tmpdir, "auth.db")
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        for u in users:
            if u is not None:
                db.add(u)
        db.commit()
        db.close()
        return engine, Session

    def _auth_app(self, token, users=(), precreate=None, patch_verifier=True):
        """App with /me depending on the real get_current_user.

        verify_firebase_token is patched to return ``token`` (or to raise if
        ``token is None``). Only ``get_db`` is overridden. Returns
        (client, Session, _WriteCounter, engine).
        """
        users = list(precreate if precreate is not None else users)
        engine, Session = self._make_engine(users)
        counter = _WriteCounter(engine)

        app = FastAPI()

        @app.get("/me")
        def me(user: User = Depends(get_current_user)):
            return {"id": user.id, "email": user.email, "name": user.name,
                    "picture": user.profile_picture_url}

        app.dependency_overrides[get_db] = _session_overrider(Session)

        if patch_verifier and token is not None:
            self._verifier = patch.object(auth_module, "verify_firebase_token", return_value=token)
            self._verifier.start()

        client = TestClient(app)
        return client, Session, counter, engine

    def tearDown(self):
        verifier = getattr(self, "_verifier", None)
        if verifier is not None:
            verifier.stop()
            self._verifier = None
        tmpdir = getattr(self, "_tmpdir", None)
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
            self._tmpdir = None


class TestAuthReadOnly(unittest.TestCase, AuthHarnessMixin):
    def test_missing_authorization_returns_401(self):
        client, _, _, _ = self._auth_app(token={"uid": "u", "email": "e", "name": "n"},
                                         patch_verifier=False)
        resp = client.get("/me")
        self.assertEqual(resp.status_code, 401)

    def test_invalid_expired_token_rejected(self):
        client, _, _, _ = self._auth_app(token=None, patch_verifier=False)
        with patch.object(auth_module, "verify_firebase_token", side_effect=Exception("expired")):
            resp = client.get("/me", headers={"Authorization": "Bearer deadbeef"})
        self.assertEqual(resp.status_code, 401)
        self.assertNotIn("deadbeef", resp.text)
        self.assertIn("Invalid or expired", resp.json()["detail"])

    def test_valid_token_existing_user_succeeds(self):
        existing = User(id=self.USER_A["id"], firebase_uid=self.USER_A["firebase_uid"],
                        email=self.USER_A["email"], name=self.USER_A["name"],
                        profile_picture_url=self.USER_A["picture"])
        client, _, _, _ = self._auth_app(
            token={"uid": self.USER_A["firebase_uid"], "email": "whatever@x.com",
                   "name": "CHANGED", "picture": "http://y.png"},
            precreate=[existing],
        )
        resp = client.get("/me", headers={"Authorization": "Bearer good-token"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Token claims must NOT overwrite the local profile on an existing user.
        self.assertEqual(body["id"], self.USER_A["id"])
        self.assertEqual(body["email"], self.USER_A["email"])
        self.assertEqual(body["name"], self.USER_A["name"])
        self.assertEqual(body["picture"], self.USER_A["picture"])

    def test_existing_user_auth_emits_zero_writes(self):
        existing = User(id=self.USER_A["id"], firebase_uid=self.USER_A["firebase_uid"],
                        email=self.USER_A["email"], name=self.USER_A["name"],
                        profile_picture_url=self.USER_A["picture"])
        client, _, counter, _ = self._auth_app(
            token={"uid": self.USER_A["firebase_uid"], "email": "e", "name": "n"},
            precreate=[existing],
        )
        counter.reset()
        resp = client.get("/me", headers={"Authorization": "Bearer good-token"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(counter.w_kinds, {"INSERT": 0, "UPDATE": 0, "DELETE": 0})
        self.assertGreaterEqual(counter.select_count(), 1)

    def test_existing_user_updated_at_unchanged(self):
        from datetime import datetime, timezone
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        existing = User(id=self.USER_A["id"], firebase_uid=self.USER_A["firebase_uid"],
                        email=self.USER_A["email"], name=self.USER_A["name"])
        existing.updated_at = ts
        client, Session, _, _ = self._auth_app(
            token={"uid": self.USER_A["firebase_uid"], "email": "e", "name": "n"},
            precreate=[existing],
        )
        client.get("/me", headers={"Authorization": "Bearer good-token"})
        s = Session()
        row = s.query(User).filter(User.id == self.USER_A["id"]).first()
        self.assertEqual(row.updated_at.replace(tzinfo=timezone.utc), ts)
        s.close()


class TestFirstLogin(unittest.TestCase, AuthHarnessMixin):
    def test_first_login_provisions_user(self):
        token = {"uid": "new_uid", "email": "new@x.com", "name": "New User",
                 "picture": "http://x/p.png"}
        client, Session, _, _ = self._auth_app(token=token)
        resp = client.get("/me", headers={"Authorization": "Bearer first-token"})
        self.assertEqual(resp.status_code, 200)
        s = Session()
        rows = s.query(User).filter(User.firebase_uid == "new_uid").all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].email, "new@x.com")
        self.assertEqual(rows[0].name, "New User")
        self.assertEqual(rows[0].profile_picture_url, "http://x/p.png")
        s.close()

    def test_first_login_provisions_with_only_inserts(self):
        token = {"uid": "new_uid2", "email": "n2@x.com", "name": "N2"}
        client, _, counter, _ = self._auth_app(token=token)
        counter.reset()
        resp = client.get("/me", headers={"Authorization": "Bearer ft"})
        self.assertEqual(resp.status_code, 200)
        kinds = counter.w_kinds
        self.assertEqual(kinds["INSERT"], 1)
        self.assertEqual(kinds["UPDATE"], 0)
        self.assertEqual(kinds["DELETE"], 0)

    def test_firebase_uid_uniqueness_enforced(self):
        token = {"uid": "dup_uid", "email": "d@x.com", "name": "D"}
        client, Session, _, _ = self._auth_app(token=token)
        client.get("/me", headers={"Authorization": "Bearer a"})
        client2, Session2, _, _ = self._auth_app(token=token)
        client2.get("/me", headers={"Authorization": "Bearer b"})
        s = Session2()
        count = s.query(User).filter(User.firebase_uid == "dup_uid").count()
        self.assertEqual(count, 1)
        s.close()

    def test_parallel_first_login_race_does_not_duplicate(self):
        # Deterministic branch test of the IntegrityError race-recovery path: a
        # "winning" user already exists, but the losing request's initial lookup
        # misses (simulating the winner's transaction not yet visible). The
        # losing request attempts a real INSERT that the unique constraint
        # rejects, then rolls back and re-queries, returning the existing winner.
        winner = User(id="winner", firebase_uid="race_uid", email="w@x.com", name="W")
        _, Session, _, _ = self._auth_app(
            token={"uid": "race_uid", "email": "w@x.com", "name": "W"},
            precreate=[winner],
        )
        s = Session()
        real_query = s.query
        calls = {"lookup": 0}

        def patched_query(model):
            q = real_query(model)
            if model is User:
                orig_first = q.first

                def first():
                    calls["lookup"] += 1
                    if calls["lookup"] == 1:
                        return None  # loser cannot see the winner's row yet
                    return orig_first()

                q.first = first
            return q

        s.query = patched_query

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="race-token")
        with patch.object(auth_module, "verify_firebase_token",
                          return_value={"uid": "race_uid", "email": "w@x.com", "name": "W"}):
            result = auth_module.get_current_user(request=None, credentials=creds, db=s)
        self.assertEqual(result.firebase_uid, "race_uid")
        self.assertEqual(result.email, "w@x.com")
        s.close()

        check = Session()
        count = check.query(User).filter(User.firebase_uid == "race_uid").count()
        self.assertEqual(count, 1)
        check.close()

    def test_concurrent_first_login_true_concurrency_single_row(self):
        # Two real threads race first-login for the same Firebase UID against a
        # shared file-backed DB. The unique constraint plus the IntegrityError
        # recovery must yield exactly one local row, and both threads must end
        # up with the same existing (single) user.
        import threading
        _, Session, _, engine = self._auth_app(
            token={"uid": "RACE", "email": "r@x.com", "name": "R"},
            precreate=[],
        )
        barrier = threading.Barrier(2)
        results = []

        def work():
            s = Session()
            try:
                creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")
                barrier.wait()
                with patch.object(auth_module, "verify_firebase_token",
                                  return_value={"uid": "RACE", "email": "r@x.com", "name": "R"}):
                    u = auth_module.get_current_user(request=None, credentials=creds, db=s)
                results.append(u.id)
            finally:
                s.close()

        t1 = threading.Thread(target=work)
        t2 = threading.Thread(target=work)
        t1.start(); t2.start(); t1.join(); t2.join()

        check = Session()
        count = check.query(User).filter(User.firebase_uid == "RACE").count()
        ids = check.query(User).filter(User.firebase_uid == "RACE").all()
        check.close()

        self.assertEqual(count, 1)
        # Both racing requests resolved to the SAME single created user.
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], ids[0].id)


class TestAuthorization(unittest.TestCase, AuthHarnessMixin):
    def _isolated_app(self, users):
        engine, Session = self._make_engine(users)
        app = FastAPI()

        @app.get("/resource")
        def resource(user: User = Depends(get_current_user)):
            return {"owner": user.id}

        app.dependency_overrides[get_db] = _session_overrider(Session)
        return TestClient(app), Session

    def test_user_a_cannot_access_user_b(self):
        user_a = User(id="a", firebase_uid="fb_a", email="a@x.com", name="A")
        user_b = User(id="b", firebase_uid="fb_b", email="b@x.com", name="B")
        client, _ = self._isolated_app([user_a, user_b])

        with patch.object(auth_module, "verify_firebase_token",
                          return_value={"uid": "fb_a", "email": "a@x.com", "name": "A"}):
            resp = client.get("/resource", headers={"Authorization": "Bearer a-token"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["owner"], "a")

        with patch.object(auth_module, "verify_firebase_token",
                          return_value={"uid": "fb_b", "email": "b@x.com", "name": "B"}):
            resp2 = client.get("/resource", headers={"Authorization": "Bearer b-token"})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["owner"], "b")

    def test_uid_comes_only_from_verified_token(self):
        user_a = User(id="a", firebase_uid="fb_a", email="a@x.com", name="A")
        user_b = User(id="b", firebase_uid="fb_b", email="b@x.com", name="B")
        client, _ = self._isolated_app([user_a, user_b])
        with patch.object(auth_module, "verify_firebase_token",
                          return_value={"uid": "fb_a", "email": "a@x.com", "name": "A"}):
            resp = client.get(
                "/resource",
                headers={"Authorization": "Bearer a-token",
                         "X-User-Id": "someone-else", "X-UID": "fb_b", "uid": "fb_b"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["owner"], "a")


class TestLoggingTokenFree(unittest.TestCase, AuthHarnessMixin):
    def _capture(self):
        records = []

        class Buf(logging.Handler):
            def emit(self, rec):
                records.append(rec)

        h = Buf()
        logging.getLogger().addHandler(h)
        return records, h

    def test_successful_auth_does_not_log_tokens(self):
        existing = User(id=self.USER_A["id"], firebase_uid=self.USER_A["firebase_uid"],
                        email=self.USER_A["email"], name=self.USER_A["name"])
        client, _, _, _ = self._auth_app(
            token={"uid": self.USER_A["firebase_uid"], "email": "e", "name": "n"},
            precreate=[existing],
        )
        records, h = self._capture()
        try:
            resp = client.get("/me", headers={"Authorization": "Bearer SUPERTOKEN"})
            self.assertEqual(resp.status_code, 200)
        finally:
            logging.getLogger().removeHandler(h)
        text = "\n".join(str(r.getMessage()) for r in records)
        self.assertNotIn("SUPERTOKEN", text)
        self.assertNotIn("Bearer", text)

    def test_auth_failure_logs_token_free(self):
        client, _, _, _ = self._auth_app(token=None, patch_verifier=False)
        records, h = self._capture()
        try:
            with patch.object(auth_module, "verify_firebase_token", side_effect=Exception("expired")):
                resp = client.get("/me", headers={"Authorization": "Bearer BADTOKEN"})
        finally:
            logging.getLogger().removeHandler(h)
        self.assertEqual(resp.status_code, 401)
        text = "\n".join(str(r.getMessage()) for r in records)
        self.assertNotIn("BADTOKEN", text)
        self.assertNotIn("Bearer", text)


class TestProfileUpdateStillWrites(unittest.TestCase, AuthHarnessMixin):
    def test_explicit_profile_update_performs_write(self):
        from app.api.profile import router as profile_router
        from app.models.profile import Profile
        user = User(id="u1", firebase_uid="fb1", email="u@x.com", name="U")

        engine, Session = self._make_engine([user])
        counter = _WriteCounter(engine)
        db = Session()
        db.add(Profile(id="p1", user_id="u1"))
        db.commit()
        db.close()

        app = FastAPI()
        app.include_router(profile_router)

        app.dependency_overrides[get_db] = _session_overrider(Session)

        def override_gc():
            s = Session()
            try:
                return s.query(User).filter(User.id == "u1").first()
            finally:
                s.close()

        app.dependency_overrides[get_current_user] = override_gc
        client = TestClient(app)

        counter.reset()
        resp = client.put("/profile", json={"location": "Berlin"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(counter.w_kinds["UPDATE"], 1)


if __name__ == "__main__":
    unittest.main()
