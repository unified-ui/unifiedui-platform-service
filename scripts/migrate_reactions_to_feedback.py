"""Migrate reactions stored in the agent-service MongoDB into the platform-service ``message_feedback`` SQL table.

Idempotent: existing (tenant_id, message_id, user_id) entries are updated, not duplicated.
Run with: ``uv run python scripts/migrate_reactions_to_feedback.py [--dry-run]``.
"""

import argparse
import os
import sys
import uuid
from typing import Any

from pymongo import MongoClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from unifiedui.core.database.models import Conversation, MessageFeedback

REACTION_TO_RATING = {
    "thumbs_up": "THUMBS_UP",
    "thumbs_down": "THUMBS_DOWN",
}


def _get_env(name: str, default: str | None = None) -> str:
    """Return the value of an env var or raise if missing and no default."""
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _normalise_reaction(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Map a Mongo reaction document onto the MessageFeedback shape, or return None if unmappable."""
    reaction_value = doc.get("reaction")
    rating = REACTION_TO_RATING.get(str(reaction_value))
    if rating is None:
        return None

    tenant_id = doc.get("tenantId") or doc.get("tenant_id")
    conversation_id = doc.get("conversationId") or doc.get("conversation_id")
    message_id = doc.get("messageId") or doc.get("message_id")
    user_id = doc.get("userId") or doc.get("user_id")
    feedback_text = doc.get("feedbackText") or doc.get("feedback_text") or None

    if not tenant_id or not conversation_id or not message_id or not user_id:
        return None

    return {
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "user_id": user_id,
        "rating": rating,
        "comment": feedback_text,
    }


def migrate(*, dry_run: bool) -> tuple[int, int, int, int]:
    """Run the migration. Returns ``(scanned, inserted, updated, skipped_no_conversation)`` counts."""
    mongo_uri = _get_env(
        "MONGODB_URI",
        "mongodb://admin:admin@localhost:27017/?authSource=admin",
    )
    mongo_db_name = _get_env("MONGODB_DATABASE", "unifiedui")
    pg_url = _get_env(
        "DATABASE_URL",
        "postgresql://unifiedui:unifiedui_password@localhost:5432/unifiedui",
    )

    mongo_client: MongoClient[dict[str, Any]] = MongoClient(mongo_uri)
    mongo_collection = mongo_client[mongo_db_name]["reactions"]

    engine = create_engine(pg_url)

    scanned = 0
    inserted = 0
    updated = 0
    skipped_no_conversation = 0

    with Session(engine) as session:
        for doc in mongo_collection.find({}):
            scanned += 1
            normalised = _normalise_reaction(doc)
            if normalised is None:
                continue

            conv_stmt = select(Conversation.id).where(
                Conversation.id == normalised["conversation_id"],
                Conversation.tenant_id == normalised["tenant_id"],
            )
            if session.execute(conv_stmt).scalar_one_or_none() is None:
                skipped_no_conversation += 1
                continue

            stmt = select(MessageFeedback).where(
                MessageFeedback.tenant_id == normalised["tenant_id"],
                MessageFeedback.message_id == normalised["message_id"],
                MessageFeedback.user_id == normalised["user_id"],
            )
            existing = session.execute(stmt).scalar_one_or_none()

            if existing is None:
                entry = MessageFeedback(
                    id=str(uuid.uuid4()),
                    tenant_id=normalised["tenant_id"],
                    conversation_id=normalised["conversation_id"],
                    message_id=normalised["message_id"],
                    user_id=normalised["user_id"],
                    rating=normalised["rating"],
                    reasons=[],
                    comment=normalised["comment"],
                )
                if not dry_run:
                    session.add(entry)
                inserted += 1
            else:
                existing.rating = normalised["rating"]
                existing.comment = normalised["comment"]
                if existing.reasons is None:
                    existing.reasons = []
                updated += 1

        if not dry_run:
            session.commit()

    mongo_client.close()
    engine.dispose()
    return scanned, inserted, updated, skipped_no_conversation


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Scan and report only; do not write to PostgreSQL.")
    args = parser.parse_args()

    scanned, inserted, updated, skipped = migrate(dry_run=args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] scanned={scanned} inserted={inserted} updated={updated} skipped_no_conversation={skipped}")
    sys.exit(0)


if __name__ == "__main__":
    main()
