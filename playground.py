import os

from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# STEP-1 => get the url from env file

DATABASE_URL = os.getenv("DATABASE_URL")

print(DATABASE_URL)

# STEP-2 => the road to the DATABASE

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    version = conn.execute(text("SELECT version()")).scalar()
    print(f"connected to {version.split(",")[0]}")


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "student_records"

    id = Column(String, primary_key=True)
    name = Column(String(50), nullable=False)
    age = Column(Integer, nullable=False)
    course = Column(String(50), nullable=False)
    email = Column(String, nullable=False, unique=True)
    marks = Column(Integer, nullable=False)


Base.metadata.create_all(bind=engine)
print("Table ready...")

sessionLocal = sessionmaker(bind=engine)

db = sessionLocal()