"""Create tables and seed practice sentences if the table is empty."""

from .database import Base, SessionLocal, engine
from .models import Sentence

# Easy, everyday sentences — short and natural, no tongue twisters.
SEED_SENTENCES = [
    "I like to drink coffee in the morning.",
    "She is reading a good book.",
    "We are going to the park today.",
    "The sun is bright and warm.",
    "He has a black cat and a brown dog.",
    "Please open the window.",
    "My favorite color is blue.",
    "Can you help me find my keys?",
    "They are eating lunch together.",
    "The weather is nice this afternoon.",
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Sentence).count() == 0:
            db.add_all(Sentence(text=t) for t in SEED_SENTENCES)
            db.commit()
    finally:
        db.close()


def reseed() -> None:
    """Replace all sentences (and their attempts) with the current seed set."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Sentence).delete()  # cascades to attempts
        db.add_all(Sentence(text=t) for t in SEED_SENTENCES)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    if "--reseed" in sys.argv:
        reseed()
        print("Database reseeded.")
    else:
        init_db()
        print("Database initialized and seeded.")
