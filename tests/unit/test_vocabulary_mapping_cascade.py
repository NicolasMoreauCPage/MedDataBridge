from sqlmodel import SQLModel, Session, create_engine, select

from app.models_vocabulary import VocabularyMapping, VocabularySystem
from app.vocabularies.init import create_scenario_type_vocabularies


def test_scenario_vocabulary_mappings_are_persisted_by_relationship_cascade() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        systems = create_scenario_type_vocabularies()
        for system in systems:
            session.add(system)
        session.commit()

        assert len(session.exec(select(VocabularySystem)).all()) == 3
        assert len(session.exec(select(VocabularyMapping)).all()) == 6
