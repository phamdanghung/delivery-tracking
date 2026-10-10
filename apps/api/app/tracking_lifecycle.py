from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.database import audit


def transition(db: Connection, request: Request, actor: UUID, delivery: UUID, status: str) -> None:
    if status == "DELIVERED":
        db.execute(
            text("""UPDATE tracking_tokens SET expires_at=now()+interval '1 hour'
            WHERE delivery_id=:id AND revoked_at IS NULL AND trip_stop_id IN
            (SELECT id FROM trip_stops WHERE delivery_id=:id AND trip_id=
              (SELECT t.id FROM trip_stops cs JOIN trips t ON t.id=cs.trip_id
               WHERE cs.delivery_id=:id ORDER BY t.created_at DESC,t.id DESC LIMIT 1))"""),
            {"id": delivery},
        )
    elif status in {"FAILED", "CANCELLED", "RESCHEDULED"}:
        identifiers: Any = db.execute(
            text("""UPDATE tracking_tokens SET revoked_at=now()
            WHERE delivery_id=:id AND revoked_at IS NULL RETURNING id"""),
            {"id": delivery},
        )
        for identifier in identifiers.scalars():
            audit(
                db, request, actor, "REVOKE", "tracking_link", identifier, after={"reason": status}
            )
