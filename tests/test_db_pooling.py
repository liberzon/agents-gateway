"""Every PostgresDb must ride the one shared engine.

Supabase's session-mode pooler caps this project at 15 clients. A
`PostgresDb(db_url=...)` per agent/team builds its own pool, and agents are cached
per (user, session), so conversations piled up pools until the pooler refused
connections with "FATAL: (EMAXCONNSESSION) max clients reached ... pool_size: 15".
Session writes then failed, chat history vanished, and agents kept asking the user
to repeat themselves.
"""

import pathlib
import re

import pytest

from agents.agent import get_agent_db
from api.routes.v2.teams import get_team_db
from db.session import db_engine

REPO = pathlib.Path(__file__).resolve().parent.parent
# The only places allowed to construct a PostgresDb (they pass the shared engine).
ALLOWED = {"agents/agent.py", "api/routes/v2/teams.py"}


def test_agent_and_team_dbs_use_the_shared_engine():
    assert get_agent_db("a_test_s").db_engine is db_engine
    assert get_team_db(session_table="t_test_s").db_engine is db_engine


def test_db_instances_are_cached_per_table():
    assert get_agent_db("a_test_s") is get_agent_db("a_test_s")
    assert get_agent_db("a_test_s") is not get_agent_db("a_other_s")
    assert get_team_db(session_table="t_test_s") is get_team_db(session_table="t_test_s")


def test_the_shared_pool_stays_under_the_supabase_client_cap():
    """5 + 3 overflow = 8 connections at most, for the whole process."""
    assert db_engine.pool.size() + db_engine.pool._max_overflow <= 12
    assert db_engine.pool._pre_ping is True


@pytest.mark.parametrize(
    "path",
    sorted(
        p
        for p in REPO.rglob("*.py")
        if ".venv" not in p.parts and "tests" not in p.parts and "PostgresDb(" in p.read_text()
    ),
)
def test_no_module_builds_a_postgresdb_with_its_own_url(path):
    rel = path.relative_to(REPO).as_posix()
    # comments may quote the anti-pattern (they explain this very rule)
    text = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("#"))
    assert not re.search(r"PostgresDb\(\s*\n?\s*db_url=", text), (
        f"{rel}: PostgresDb(db_url=...) opens a second connection pool — pass the "
        f"shared engine via get_agent_db()/get_team_db() instead"
    )
    assert rel in ALLOWED, f"{rel}: construct PostgresDb only via the cached factories"
