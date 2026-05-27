from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PromptData:
    """Data class for prompt information."""

    id: str
    name: str
    template: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "template": self.template,
            "description": self.description,
            "tags": self.tags,
            "tools": self.tools,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptData":
        """Create from dictionary representation."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            id=data["id"],
            name=data["name"],
            template=data["template"],
            description=data.get("description"),
            tags=data.get("tags", []),
            tools=data.get("tools", []),
            version=data.get("version", 1),
            created_at=created_at,
            updated_at=updated_at,
            is_active=data.get("is_active", True),
        )
