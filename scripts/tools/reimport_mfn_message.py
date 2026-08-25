"""Réimporte le dernier message MFN correspondant à la corrélation configurée."""

from sqlmodel import select

from app.db import session_factory
from app.models_shared import MessageLog
from app.models_structure import GHTContext
from app.services.mfn_importer import import_mfn


CORRELATION_PATTERN = "%20250206141011%"
GHT_CONTEXT_ID = 2


def main() -> None:
    with session_factory() as session:
        message = session.exec(
            select(MessageLog)
            .where(MessageLog.correlation_id.like(CORRELATION_PATTERN))
            .order_by(MessageLog.id.desc())
        ).first()
        if not message:
            raise SystemExit("Message non trouvé.")

        ght = session.get(GHTContext, GHT_CONTEXT_ID)
        if not ght:
            raise SystemExit(f"GHT id={GHT_CONTEXT_ID} non trouvé.")

        print(f"Message trouvé: ID={message.id}, Type={message.message_type}, endpoint={message.endpoint_id}")
        result = import_mfn(message.payload, session, ght)
        session.commit()
        print("Résultat:")
        for entity_type, count in result.items():
            print(f"  {entity_type}: {count}")


if __name__ == "__main__":
    main()
