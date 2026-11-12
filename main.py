# PART-1 => load .env file and import all important libraries

import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)
from sqlalchemy import Column, Integer, String, create_engine, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")

print(DATABASE_URL)


# PART-2 => create the engine (connection to postgresSQL)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    version = conn.execute(text("SELECT version()")).scalar()
    print(f"connected to {version.split(",")[0]}")


# PART-3 => create sessionLocal and Base

sessionLocal = sessionmaker(bind=engine)

db = sessionLocal()


class Base(DeclarativeBase):
    pass


# PART-4 => create the student database


class StudentDB(Base):
    __tablename__ = "student_records"

    id = Column(String, primary_key=True)
    name = Column(String(50), nullable=False)
    age = Column(Integer, nullable=False)
    course = Column(String(50), nullable=False)
    email = Column(String, nullable=False, unique=True)
    marks = Column(Integer, nullable=False)


Base.metadata.create_all(bind=engine)
print("Table ready...")

# Part 5: Pydantic schemas for input (StudentCreate, StudentUpdate)


class StudentCreate(BaseModel):

    id: str = Field(..., examples=["S001"])
    name: str = Field(..., min_length=2, max_length=50)
    age: int = Field(..., gt=0, lt=100)
    email: EmailStr
    course: str = Field(..., max_length=50)
    marks: int = Field(..., gt=0, le=100)

    @field_validator("name")
    @classmethod
    def check_name(cls, value):
        if not value.replace(" ", "").isalpha():
            raise ValueError("the name must contain only letters and space")

        return value.title()


class StudentUpdate(BaseModel):

    id: str | None = Field(None, examples=["S001"])
    name: str | None = Field(None, min_length=2, max_length=50)
    age: int | None = Field(None, gt=0, lt=100)

    course: str | None = Field(None, max_length=50)
    marks: int | None = Field(None, gt=0, le=100)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def check_name(cls, value):
        if not value.replace(" ", "").isalpha():
            raise ValueError("the name must contain only letters and space")

        return value.title()


# Part 6: Pydantic schemas for output (StudentResponse, StudentPage, Message)


class StudentResponse(StudentCreate):

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def grade(self) -> str:

        if self.marks >= 90:
            return "A+"

        elif self.marks >= 80:
            return "A"

        elif self.marks >= 70:
            return "B"

        elif self.marks >= 60:
            return "C"

        elif self.marks >= 50:
            return "D"

        else:
            return "FAIL"


# Part 7: get_db() - one session per request
# Opens a session, gives it to the endpoint, always closes it, replaces load_data/
# save_data


# Opens a session, pauses at yield while the endpoint doest its work and once the
# endpoint completed it's work the session will be closed.
def get_db():
    db = sessionLocal()
    try:
        yield db

    finally:
        db.close()


# Part 8: Create the FastAPI app


app = FastAPI()


# Part 9: GET one student


@app.get("/student/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: str = Path(..., description="get one student id"),
    db: Session = Depends(get_db),
):
    student = db.get(StudentDB, student_id)

    if student is None:
        raise HTTPException(
            status_code=404, detail=f"student with id '{student_id}' not found"
        )

    return student


# Part 10: POST - create a student


@app.post("/CreateStudent", response_model=StudentResponse, status_code=201)
def create_student(student: StudentCreate, db: Session = Depends(get_db)):

    if db.get(StudentDB, student.id):
        raise HTTPException(
            status_code=400, detail=f"student with id '{student.id}' already exist"
        )

    new_student = StudentDB(**student.model_dump())

    db.add(new_student)

    try:
        db.commit()

    except IntegrityError:
        
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"email '{student.email}' alerady used by another student",
        )

    db.refresh(new_student)

    return new_student


# Part 11: PUT - update a student


@app.put("/UpdateStudent/{student_id}")
def update_student(
    student_update: StudentUpdate,
    student_id: str = Path(..., description="the id of the student"),
):

    student = db.get(StudentDB, student_id)

    if student is None:
        raise HTTPException(
            status_code=400, detail=f"student with id '{student_id}' does not exists..."
        )

    changes = student_update.model_dump(exclude_unset=True)

    for key, values in changes.items():
        setattr(student, key, values)

    try:
        db.commit()

    except IntegrityError:
        
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"email '{student.email}' alerady used by another student",
        )

    db.refresh(student)
    return student


# Part 12: DELETE - remove a student


@app.delete("/DeleteStudent/{student_id}")
def delete_student(
    student_id: str = Path(..., description="the id of the student"),
    db: Session = Depends(get_db),
):

    student = db.get(StudentDB, student_id)

    if student is None:
        raise HTTPException(
            status_code=404, detail=f"student with id '{student_id}' not found"
        )

    db.delete(student)

    db.commit()

    return {"message": f"student with id '{student_id}' has deleted..."}


# Part 13: GET all students (filter + sort + paginate)

SORT_FIELDS = ["marks", "age", "name"]
SORT_ORDER = ["asc", "desc"]


@app.get("/students")
def get_all(
    course: str | None = Query(
        None, description="show only student in this course", examples=["Python"]
    ),
    sort_by: str | None = Query(None, description="sort by name, age or marks"),
    order: str = Query("asc", description="asc or desc", examples=["desc"]),
    page: int = Query(1, ge=1, description="which page do you want (start from 1)"),
    limit: int = Query(
        2, ge=1, le=100, description="how many pages you want (from 1 to 100)"
    ),
    db: Session = Depends(get_db),
):

    if sort_by is not None and sort_by not in SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"invalid sort_by '{sort_by}', choose from {SORT_FIELDS}",
        )

    if order not in SORT_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"invalid order '{order}', choose from {SORT_ORDER}",
        )

    query = db.query(StudentDB)

    if course:
        query = query.filter(func.lower(StudentDB.course) == course.lower())

    total_student = query.count()

    if sort_by:

        column = getattr(StudentDB, sort_by)

        if order == "desc":

            query = query.order_by(column.desc())

        else:
            query = query.order_by(column.asc())
    else:

        query = query.order_by(StudentDB.id)

    start = (page - 1) * limit
    student = query.offset(start).limit(limit).all()

    return {
        "page": page,
        "limit": limit,
        "total student": total_student,
        "students": student,
    }
