import json
import os
import unittest
from typing import Any

os.environ["TESTING"] = "true"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.db_models import SkillDB
from db.skill_crud import (
    create_skill,
    get_all_skills,
    get_skill,
    soft_delete_skill,
    update_skill,
)


class TestSkillCRUD(unittest.TestCase):
    """Test skill CRUD operations with SQLite in-memory database."""

    engine: Any = None
    SessionLocal: Any = None

    @classmethod
    def setUpClass(cls):  # type: ignore[override]
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # Only create the skills table (Base.metadata.create_all fails with
        # schema-qualified tables like PromptDB that SQLite doesn't support)
        SkillDB.__table__.create(bind=cls.engine, checkfirst=True)  # type: ignore[attr-defined]
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        SkillDB.__table__.drop(bind=cls.engine, checkfirst=True)  # type: ignore[attr-defined]

    def setUp(self):
        self.db = self.SessionLocal()
        # Clean up skills table before each test
        self.db.query(SkillDB).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_create_skill(self):
        """Create a skill and verify all fields are stored correctly."""
        skill = create_skill(
            db=self.db,
            skill_id="skill-1",
            name="Research Skill",
            instructions="Search and summarize documents",
            description="A skill for research tasks",
            category="research",
            references=[{"name": "ref1", "content": "some reference"}],
            scripts=[{"name": "script1", "content": "print('hello')"}],
            allowed_tools=["search", "summarize"],
            tags=["research", "ai"],
        )

        self.assertEqual(skill.id, "skill-1")
        self.assertEqual(skill.name, "Research Skill")
        self.assertEqual(skill.instructions, "Search and summarize documents")
        self.assertEqual(skill.description, "A skill for research tasks")
        self.assertEqual(skill.category, "research")
        self.assertEqual(json.loads(skill.references), [{"name": "ref1", "content": "some reference"}])  # type: ignore[arg-type]
        self.assertEqual(json.loads(skill.scripts), [{"name": "script1", "content": "print('hello')"}])  # type: ignore[arg-type]
        self.assertEqual(json.loads(skill.allowed_tools), ["search", "summarize"])  # type: ignore[arg-type]
        self.assertEqual(json.loads(skill.tags), ["research", "ai"])  # type: ignore[arg-type]
        self.assertTrue(skill.is_active)
        self.assertIsNotNone(skill.created_at)
        self.assertIsNotNone(skill.updated_at)

    def test_get_skill(self):
        """Get a skill by ID."""
        create_skill(
            db=self.db,
            skill_id="skill-get",
            name="Get Skill",
            instructions="Test instructions",
        )

        result = get_skill(self.db, "skill-get")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "skill-get")  # type: ignore[union-attr]
        self.assertEqual(result.name, "Get Skill")  # type: ignore[union-attr]

    def test_get_skill_not_found(self):
        """Get a non-existent skill returns None."""
        result = get_skill(self.db, "non-existent")
        self.assertIsNone(result)

    def test_get_all_skills(self):
        """List active skills."""
        create_skill(db=self.db, skill_id="skill-a", name="Alpha", instructions="instr a")
        create_skill(db=self.db, skill_id="skill-b", name="Beta", instructions="instr b")

        # Soft-delete one
        soft_delete_skill(self.db, "skill-b")

        skills = get_all_skills(self.db)
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].id, "skill-a")

    def test_get_all_skills_with_category(self):
        """Filter skills by category."""
        create_skill(db=self.db, skill_id="skill-c1", name="Cat1 Skill", instructions="instr", category="cat1")
        create_skill(db=self.db, skill_id="skill-c2", name="Cat2 Skill", instructions="instr", category="cat2")
        create_skill(db=self.db, skill_id="skill-c3", name="Cat1 Skill 2", instructions="instr", category="cat1")

        skills = get_all_skills(self.db, category="cat1")
        self.assertEqual(len(skills), 2)
        for s in skills:
            self.assertEqual(s.category, "cat1")

    def test_update_skill(self):
        """Update name and description of an existing skill."""
        create_skill(
            db=self.db,
            skill_id="skill-upd",
            name="Original Name",
            instructions="Original instructions",
            description="Original description",
        )

        updated = update_skill(
            db=self.db,
            skill_id="skill-upd",
            name="Updated Name",
            description="Updated description",
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "Updated Name")  # type: ignore[union-attr]
        self.assertEqual(updated.description, "Updated description")  # type: ignore[union-attr]
        # Instructions should remain unchanged
        self.assertEqual(updated.instructions, "Original instructions")  # type: ignore[union-attr]

    def test_update_skill_not_found(self):
        """Update a non-existent skill returns None."""
        result = update_skill(self.db, skill_id="no-such-skill", name="Nope")
        self.assertIsNone(result)

    def test_soft_delete_skill(self):
        """Soft delete sets is_active to False."""
        create_skill(db=self.db, skill_id="skill-del", name="To Delete", instructions="instr")

        result = soft_delete_skill(self.db, "skill-del")
        self.assertTrue(result)

        # Should not be found by get_skill (which filters active only)
        self.assertIsNone(get_skill(self.db, "skill-del"))

        # But should exist in DB with is_active=False
        raw = self.db.query(SkillDB).filter(SkillDB.id == "skill-del").first()
        self.assertIsNotNone(raw)
        self.assertFalse(raw.is_active)  # type: ignore[union-attr]

    def test_soft_delete_not_found(self):
        """Soft delete of non-existent skill returns False."""
        result = soft_delete_skill(self.db, "no-such-skill")
        self.assertFalse(result)

    def test_create_reactivates_inactive(self):
        """Creating a skill with the same ID as an inactive skill reactivates it."""
        create_skill(db=self.db, skill_id="skill-react", name="Original", instructions="original instr")
        soft_delete_skill(self.db, "skill-react")

        # Verify it's inactive
        self.assertIsNone(get_skill(self.db, "skill-react"))

        # Create again with same ID
        reactivated = create_skill(
            db=self.db,
            skill_id="skill-react",
            name="Reactivated",
            instructions="new instructions",
            description="now reactivated",
        )

        self.assertTrue(reactivated.is_active)
        self.assertEqual(reactivated.name, "Reactivated")
        self.assertEqual(reactivated.instructions, "new instructions")
        self.assertEqual(reactivated.description, "now reactivated")

        # Should be retrievable again
        fetched = get_skill(self.db, "skill-react")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Reactivated")  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
