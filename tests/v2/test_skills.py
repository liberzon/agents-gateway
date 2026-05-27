import unittest
from unittest.mock import patch

from db.db_models import SkillDB
from tests.test_utils import create_test_client


class TestV2SkillsAPI(unittest.TestCase):
    """Test V2 skills API endpoints."""

    def setUp(self):
        self.client, self.app = create_test_client()
        from api.routes.v2_router import get_v2_router

        self.app.include_router(get_v2_router())

        from fastapi.testclient import TestClient

        self.client = TestClient(self.app)

        self.sample_skill = SkillDB(
            id="test-skill",
            name="Test Skill",
            instructions="Do the thing",
            description="A test skill",
            category="testing",
            references=None,
            scripts=None,
            allowed_tools='["search"]',
            tags='["test"]',
            is_active=True,
        )

    @patch("api.routes.v2.skills.create_skill")
    @patch("api.routes.v2.skills.get_skill")
    def test_create_skill(self, mock_get, mock_create):
        """POST /v2/skills returns 201 on success."""
        mock_get.return_value = None  # No existing skill
        mock_create.return_value = self.sample_skill

        response = self.client.post(
            "/v2/skills",
            json={
                "id": "test-skill",
                "name": "Test Skill",
                "instructions": "Do the thing",
                "description": "A test skill",
                "category": "testing",
                "allowed_tools": ["search"],
                "tags": ["test"],
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "test-skill")
        self.assertEqual(data["name"], "Test Skill")
        self.assertEqual(data["instructions"], "Do the thing")
        mock_create.assert_called_once()

    @patch("api.routes.v2.skills.get_skill")
    def test_create_skill_duplicate(self, mock_get):
        """POST /v2/skills returns 409 for duplicate skill."""
        mock_get.return_value = self.sample_skill

        response = self.client.post(
            "/v2/skills",
            json={
                "id": "test-skill",
                "name": "Test Skill",
                "instructions": "Do the thing",
            },
        )

        self.assertEqual(response.status_code, 409)

    @patch("api.routes.v2.skills.get_all_skills")
    def test_list_skills(self, mock_get_all):
        """GET /v2/skills returns a list of skills."""
        mock_get_all.return_value = [self.sample_skill]

        response = self.client.get("/v2/skills")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "test-skill")
        self.assertEqual(data[0]["name"], "Test Skill")

    @patch("api.routes.v2.skills.get_skill")
    def test_get_skill(self, mock_get):
        """GET /v2/skills/{id} returns the skill."""
        mock_get.return_value = self.sample_skill

        response = self.client.get("/v2/skills/test-skill")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "test-skill")
        self.assertEqual(data["name"], "Test Skill")
        self.assertEqual(data["instructions"], "Do the thing")

    @patch("api.routes.v2.skills.get_skill")
    def test_get_skill_not_found(self, mock_get):
        """GET /v2/skills/{id} returns 404 for missing skill."""
        mock_get.return_value = None

        response = self.client.get("/v2/skills/nonexistent")

        self.assertEqual(response.status_code, 404)

    @patch("api.routes.v2.skills.update_skill")
    def test_update_skill(self, mock_update):
        """PUT /v2/skills/{id} returns the updated skill."""
        updated_skill = SkillDB(
            id="test-skill",
            name="Updated Skill",
            instructions="Do the thing better",
            description="An updated skill",
            category="testing",
            references=None,
            scripts=None,
            allowed_tools='["search"]',
            tags='["test"]',
            is_active=True,
        )
        mock_update.return_value = updated_skill

        response = self.client.put(
            "/v2/skills/test-skill",
            json={
                "name": "Updated Skill",
                "instructions": "Do the thing better",
                "description": "An updated skill",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Updated Skill")
        self.assertEqual(data["instructions"], "Do the thing better")
        mock_update.assert_called_once()

    @patch("api.routes.v2.skills.soft_delete_skill")
    def test_delete_skill(self, mock_delete):
        """DELETE /v2/skills/{id} returns 204."""
        mock_delete.return_value = True

        response = self.client.delete("/v2/skills/test-skill")

        self.assertEqual(response.status_code, 204)
        mock_delete.assert_called_once()


if __name__ == "__main__":
    unittest.main()
