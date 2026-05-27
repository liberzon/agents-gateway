"""CRUD operations for TeamInfo and TeamAgent models."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.db_models import TeamAgentDB, TeamInfoDB


def create_team_info(
    db: Session,
    team_id: str,
    name: str,
    description: Optional[str] = None,
    version: str = "2.0",
    mode: str = "coordinate",
) -> TeamInfoDB:
    """
    Create a new TeamInfo record.

    Args:
        db: Database session
        team_id: Unique team identifier
        name: Display name for the team
        description: Optional description
        version: API version (defaults to "2.0")

    Returns:
        Created TeamInfoDB instance
    """
    team_info = TeamInfoDB(id=team_id, name=name, description=description, version=version, mode=mode, is_active=True)

    db.add(team_info)
    db.commit()
    db.refresh(team_info)

    logging.info(f"Created TeamInfo for {team_id}")
    return team_info


def get_team_info(db: Session, team_id: str) -> Optional[TeamInfoDB]:
    """
    Get TeamInfo by team_id.

    Args:
        db: Database session
        team_id: Team identifier

    Returns:
        TeamInfoDB instance or None if not found
    """
    return db.query(TeamInfoDB).filter(TeamInfoDB.id == team_id, TeamInfoDB.is_active).first()


def get_all_team_info(db: Session, include_inactive: bool = False) -> List[TeamInfoDB]:
    """
    Get all TeamInfo records.

    Args:
        db: Database session
        include_inactive: Whether to include inactive teams

    Returns:
        List of TeamInfoDB instances
    """
    query = db.query(TeamInfoDB)
    if not include_inactive:
        query = query.filter(TeamInfoDB.is_active)

    return query.order_by(TeamInfoDB.name).all()


def update_team_info(
    db: Session, team_id: str, name: Optional[str] = None, description: Optional[str] = None
) -> Optional[TeamInfoDB]:
    """
    Update an existing TeamInfo record.

    Args:
        db: Database session
        team_id: Team identifier
        name: New name (optional)
        description: New description (optional)

    Returns:
        Updated TeamInfoDB instance or None if not found
    """
    team_info = get_team_info(db, team_id)
    if not team_info:
        return None

    if name is not None:
        team_info.name = name  # type: ignore[assignment]
    if description is not None:
        team_info.description = description  # type: ignore[assignment]

    db.commit()
    db.refresh(team_info)

    logging.info(f"Updated TeamInfo for {team_id}")
    return team_info


def soft_delete_team_info(db: Session, team_id: str) -> bool:
    """
    Soft delete a TeamInfo record by setting is_active to False.

    Args:
        db: Database session
        team_id: Team identifier

    Returns:
        True if deleted, False if not found
    """
    team_info = get_team_info(db, team_id)
    if not team_info:
        return False

    team_info.is_active = False  # type: ignore[assignment]

    # Also soft delete all team-agent relationships
    db.query(TeamAgentDB).filter(TeamAgentDB.team_id == team_id, TeamAgentDB.is_active).update(
        {TeamAgentDB.is_active: False}
    )

    db.commit()

    logging.info(f"Soft deleted TeamInfo for {team_id}")
    return True


def team_info_exists(db: Session, team_id: str) -> bool:
    """
    Check if an active TeamInfo record exists.

    Args:
        db: Database session
        team_id: Team identifier

    Returns:
        True if exists and active, False otherwise
    """
    return db.query(TeamInfoDB).filter(TeamInfoDB.id == team_id, TeamInfoDB.is_active).first() is not None


def delete_team_info(db: Session, team_id: str) -> bool:
    """
    Hard delete a TeamInfo record and all its team-agent relationships from the database.

    Args:
        db: Database session
        team_id: Team identifier

    Returns:
        True if deleted, False if not found
    """
    try:
        # Check if team exists
        team_info = db.query(TeamInfoDB).filter(TeamInfoDB.id == team_id).first()

        if not team_info:
            logging.warning(f"Team info not found for deletion: {team_id}")
            return False

        # Delete all team-agent relationships
        db.query(TeamAgentDB).filter(TeamAgentDB.team_id == team_id).delete()

        # Delete the team
        db.delete(team_info)
        db.commit()

        logging.info(f"Hard deleted TeamInfo for {team_id}")
        return True
    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting team info: {e}")
        raise


# Team-Agent relationship CRUD operations


def add_agent_to_team(
    db: Session, team_id: str, agent_id: str, role: Optional[str] = None, order_index: Optional[int] = None
) -> TeamAgentDB:
    """
    Add an agent to a team.

    Args:
        db: Database session
        team_id: Team identifier
        agent_id: Agent identifier
        role: Optional role description
        order_index: Optional ordering index

    Returns:
        Created TeamAgentDB instance

    Raises:
        ValueError: If team or agent doesn't exist, or relationship already exists
    """
    # Check if relationship already exists
    existing = (
        db.query(TeamAgentDB)
        .filter(TeamAgentDB.team_id == team_id, TeamAgentDB.agent_id == agent_id, TeamAgentDB.is_active)
        .first()
    )

    if existing:
        raise ValueError(f"Agent {agent_id} is already in team {team_id}")

    team_agent = TeamAgentDB(team_id=team_id, agent_id=agent_id, role=role, order_index=order_index, is_active=True)

    db.add(team_agent)
    db.commit()
    db.refresh(team_agent)

    logging.info(f"Added agent {agent_id} to team {team_id}")
    return team_agent


def remove_agent_from_team(db: Session, team_id: str, agent_id: str) -> bool:
    """
    Remove an agent from a team (soft delete).

    Args:
        db: Database session
        team_id: Team identifier
        agent_id: Agent identifier

    Returns:
        True if removed, False if relationship not found
    """
    team_agent = (
        db.query(TeamAgentDB)
        .filter(TeamAgentDB.team_id == team_id, TeamAgentDB.agent_id == agent_id, TeamAgentDB.is_active)
        .first()
    )

    if not team_agent:
        return False

    team_agent.is_active = False  # type: ignore[assignment]
    db.commit()

    logging.info(f"Removed agent {agent_id} from team {team_id}")
    return True


def get_team_agents(db: Session, team_id: str) -> List[TeamAgentDB]:
    """
    Get all agents in a team.

    Args:
        db: Database session
        team_id: Team identifier

    Returns:
        List of TeamAgentDB instances ordered by order_index
    """
    return (
        db.query(TeamAgentDB)
        .filter(TeamAgentDB.team_id == team_id, TeamAgentDB.is_active)
        .order_by(TeamAgentDB.order_index.asc().nullslast(), TeamAgentDB.created_at.asc())
        .all()
    )


def get_agent_teams(db: Session, agent_id: str) -> List[TeamAgentDB]:
    """
    Get all teams an agent belongs to.

    Args:
        db: Database session
        agent_id: Agent identifier

    Returns:
        List of TeamAgentDB instances
    """
    return (
        db.query(TeamAgentDB)
        .filter(TeamAgentDB.agent_id == agent_id, TeamAgentDB.is_active)
        .order_by(TeamAgentDB.created_at.asc())
        .all()
    )


def update_team_agent_role(
    db: Session, team_id: str, agent_id: str, role: Optional[str] = None, order_index: Optional[int] = None
) -> Optional[TeamAgentDB]:
    """
    Update agent role or order in a team.

    Args:
        db: Database session
        team_id: Team identifier
        agent_id: Agent identifier
        role: New role description
        order_index: New order index

    Returns:
        Updated TeamAgentDB instance or None if not found
    """
    team_agent = (
        db.query(TeamAgentDB)
        .filter(TeamAgentDB.team_id == team_id, TeamAgentDB.agent_id == agent_id, TeamAgentDB.is_active)
        .first()
    )

    if not team_agent:
        return None

    if role is not None:
        team_agent.role = role  # type: ignore[assignment]
    if order_index is not None:
        team_agent.order_index = order_index  # type: ignore[assignment]

    db.commit()
    db.refresh(team_agent)

    logging.info(f"Updated agent {agent_id} role/order in team {team_id}")
    return team_agent


def get_team_with_agents(db: Session, team_id: str) -> Optional[Dict[str, Any]]:
    """
    Get team info with all its agents.

    Args:
        db: Database session
        team_id: Team identifier

    Returns:
        Dict with team info and agents list, or None if team not found
    """
    team_info = get_team_info(db, team_id)
    if not team_info:
        return None

    team_agents = get_team_agents(db, team_id)

    return {"team": team_info, "agents": team_agents}
