import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class TestModel(Base):
    __tablename__ = 'test_table'
    id = sa.Column(sa.UUID(as_uuid=True), primary_key=True)

engine = sa.create_engine('sqlite:///:memory:')
try:
    Base.metadata.create_all(engine)
    print("SUCCESS: Dialect-agnostic UUID works natively under SQLite in this SQLAlchemy version!")
except Exception as e:
    print(f"FAILED: {e.__class__.__name__}: {e}")
