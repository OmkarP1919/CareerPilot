"""HTTP/API-level regression tests for the saved-search REST endpoints.

These exercise the actual FastAPI route handlers in app.api.discovery rather
than the discovery_service methods directly. They cover the Phase 5C smoke-test
defect where SavedSearchResponse.model_validate() was called on the ORM object
while ``SavedSearch.criteria`` / ``SavedSearch.last_seen_keys`` are stored as
JSON text, so every saved-search response path returned 500.
"""
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.discovery import router as discovery_router
from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.schemas.discovery import DiscoveryJobHit, DiscoveryReport, SourceStatusInfo


class TestSavedSearchAPI(unittest.TestCase):
    """End-to-end API tests for /jobs/discovery/saved-searches*."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.user_a = User(id="user_a", firebase_uid="fb_ss_a", email="a@test.com", name="User A")
        self.user_b = User(id="user_b", firebase_uid="fb_ss_b", email="b@test.com", name="User B")
        db = self.Session()
        db.add_all([self.user_a, self.user_b])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(discovery_router)
        self.current_user_id = "user_a"

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == self.current_user_id).first()
            finally:
                session.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.engine.dispose()

    def _seed(
        self,
        search_id="ss_1",
        user_id="user_a",
        name="Python Remote",
        criteria=None,
        last_seen_keys=None,
    ):
        """Insert a SavedSearch row directly, exactly as the service persists it."""
        db = self.Session()
        saved = SavedSearch(
            id=search_id,
            user_id=user_id,
            name=name,
            criteria=json.dumps(criteria if criteria is not None else {"queries": ["Python Developer"]}),
            last_seen_keys=json.dumps(last_seen_keys) if last_seen_keys is not None else None,
        )
        db.add(saved)
        db.commit()
        db.refresh(saved)
        db.close()
        return saved

    def _database_criteria(self, search_id):
        db = self.Session()
        value = db.query(SavedSearch).filter(SavedSearch.id == search_id).one().criteria
        db.close()
        return value

    # ------------------------------------------------------------------
    # GET /jobs/discovery/saved-searches
    # ------------------------------------------------------------------

    def test_list_saved_searches_returns_criteria_object(self):
        self._seed(last_seen_keys=["adzuna:acme:python-dev", "jobicy:global:remote-backend"])

        response = self.client.get("/jobs/discovery/saved-searches")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        item = body[0]
        self.assertEqual(item["id"], "ss_1")
        self.assertEqual(item["name"], "Python Remote")
        # criteria must be a JSON object, never the raw stored JSON string
        self.assertIsInstance(item["criteria"], dict)
        self.assertEqual(item["criteria"], {"queries": ["Python Developer"]})
        # last_seen_count reflects the parsed list length
        self.assertEqual(item["last_seen_count"], 2)
        self.assertIsNotNone(item["created_at"])

    def test_list_saved_searches_is_user_scoped(self):
        self._seed(search_id="ss_a1", user_id="user_a", name="A Search")
        self._seed(search_id="ss_b1", user_id="user_b", name="B Search")

        response_a = self.client.get("/jobs/discovery/saved-searches")
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual([i["id"] for i in response_a.json()], ["ss_a1"])

        self.current_user_id = "user_b"
        response_b = self.client.get("/jobs/discovery/saved-searches")
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual([i["id"] for i in response_b.json()], ["ss_b1"])

    # ------------------------------------------------------------------
    # POST /jobs/discovery/saved-searches
    # ------------------------------------------------------------------

    def test_create_saved_search_returns_criteria_object(self):
        payload = {
            "name": "Backend Roles",
            "criteria": {"queries": ["Backend Developer"], "locations": ["Remote"], "remote": True},
        }
        response = self.client.post("/jobs/discovery/saved-searches", json=payload)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["name"], "Backend Roles")
        self.assertIsInstance(body["criteria"], dict)
        self.assertEqual(body["criteria"], payload["criteria"])
        self.assertEqual(body["last_seen_count"], 0)
        self.assertIsInstance(body["id"], str)
        self.assertTrue(body["id"])

        # Persistence is unchanged: criteria stored as JSON text in the DB.
        stored = self._database_criteria(body["id"])
        self.assertEqual(json.loads(stored), payload["criteria"])
        self.assertIsInstance(stored, str)

    # ------------------------------------------------------------------
    # POST /jobs/discovery/saved-searches/{search_id}/run
    # ------------------------------------------------------------------

    @patch("app.services.discovery_service.run_filtered_search")
    def test_run_saved_search_returns_valid_serialized_response(self, mock_run):
        self._seed(last_seen_keys=["adzuna:legacy:old-key"])
        mock_run.return_value = DiscoveryReport(
            total=2,
            unique_results=2,
            duplicate_count=0,
            selected_sources=["Adzuna", "Jobicy"],
            sources=[SourceStatusInfo(source="Adzuna", status="ok", jobs_fetched=2)],
            errors=[],
            total_fetched=2,
            results=[
                DiscoveryJobHit(
                    canonical_key="adzuna:acme:python-dev",
                    title="Python Developer",
                    company="Acme",
                ),
                DiscoveryJobHit(
                    canonical_key="jobicy:global:remote-backend",
                    title="Remote Backend",
                    company="Global",
                ),
            ],
        )

        response = self.client.post("/jobs/discovery/saved-searches/ss_1/run")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        saved = body["saved_search"]
        # criteria remains correctly serialized inside the nested response
        self.assertIsInstance(saved["criteria"], dict)
        self.assertEqual(saved["criteria"], {"queries": ["Python Developer"]})
        self.assertEqual(saved["id"], "ss_1")
        self.assertEqual(saved["last_seen_count"], 2)  # 2 current keys persisted
        # run replay computed new results vs. the previous last-seen keys
        self.assertEqual(body["new_results"], 2)
        self.assertEqual(body["report"]["unique_results"], 2)
        self.assertEqual(body["report"]["sources"][0]["status"], "ok")

    def test_run_saved_search_missing_id_returns_404(self):
        response = self.client.post("/jobs/discovery/saved-searches/does-not-exist/run")
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # PUT /jobs/discovery/saved-searches/{search_id}
    # ------------------------------------------------------------------

    def test_update_saved_search_returns_criteria_object(self):
        self._seed(last_seen_keys=["adzuna:acme:python-dev"])
        payload = {
            "name": "Renamed Search",
            "criteria": {"queries": ["FastAPI Engineer"], "employment_type": "Full-time"},
        }
        response = self.client.put("/jobs/discovery/saved-searches/ss_1", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "Renamed Search")
        self.assertIsInstance(body["criteria"], dict)
        self.assertEqual(body["criteria"]["queries"], ["FastAPI Engineer"])
        # unchanged fields still serialize correctly
        self.assertEqual(body["last_seen_count"], 1)

    def test_update_saved_search_partial_preserves_criteria_object(self):
        self._seed(last_seen_keys=["adzuna:acme:python-dev"])
        response = self.client.put("/jobs/discovery/saved-searches/ss_1", json={"name": "Just Name"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "Just Name")
        # criteria untouched by a partial update still parses to a dict
        self.assertIsInstance(body["criteria"], dict)
        self.assertEqual(body["criteria"], {"queries": ["Python Developer"]})
        self.assertEqual(body["last_seen_count"], 1)

    # ------------------------------------------------------------------
    # Ownership / authorization regression
    # ------------------------------------------------------------------

    def test_other_user_cannot_run_update_or_delete(self):
        self._seed()

        self.current_user_id = "user_b"
        self.assertEqual(
            self.client.post("/jobs/discovery/saved-searches/ss_1/run").status_code,
            404,
        )
        self.assertEqual(
            self.client.put(
                "/jobs/discovery/saved-searches/ss_1",
                json={"name": "Hijacked"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete("/jobs/discovery/saved-searches/ss_1").status_code,
            404,
        )

        # Owner's search is untouched and still reachable by the owner.
        self.current_user_id = "user_a"
        response = self.client.get("/jobs/discovery/saved-searches")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual([i["id"] for i in items], ["ss_1"])
        self.assertEqual(items[0]["name"], "Python Remote")

    def test_delete_owned_saved_search(self):
        self._seed()
        response = self.client.delete("/jobs/discovery/saved-searches/ss_1")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/jobs/discovery/saved-searches").json(), [])

    # ------------------------------------------------------------------
    # Edge-case JSON text handling (same semantics as _safe_json_loads)
    # ------------------------------------------------------------------

    def test_invalid_json_criteria_does_not_500(self):
        db = self.Session()
        saved = SavedSearch(id="ss_bad", user_id="user_a", name="Bad", criteria="not-json{{{")
        db.add(saved)
        db.commit()
        db.close()

        response = self.client.get("/jobs/discovery/saved-searches")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual(items[0]["criteria"], {})
        self.assertEqual(items[0]["last_seen_count"], 0)

    def test_non_dict_criteria_and_non_list_keys_fall_back_to_contract_types(self):
        # Valid JSON that is the WRONG shape for the contract fields: criteria
        # must stay a dict and last_seen_count must stay an int in the response.
        db = self.Session()
        saved = SavedSearch(
            id="ss_shape",
            user_id="user_a",
            name="Shape",
            criteria="[1, 2, 3]",
            last_seen_keys='{"not": "a list"}',
        )
        db.add(saved)
        db.commit()
        db.close()

        response = self.client.get("/jobs/discovery/saved-searches")
        self.assertEqual(response.status_code, 200)
        item = response.json()[0]
        self.assertEqual(item["criteria"], {})
        self.assertEqual(item["last_seen_count"], 0)


if __name__ == "__main__":
    unittest.main()