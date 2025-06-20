import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List
from passlib.context import CryptContext
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# Delete old DB file to avoid schema mismatch on every startup (for development only!)
DB_FILE = "books.db"
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

# --- DB Model ---
class BookDB(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    pages = Column(Integer)
    author = Column(String)
    publisher = Column(String)
    year = Column(Integer)

Base.metadata.create_all(bind=engine)  # create tables

# --- Pydantic models ---
class BookBase(BaseModel):
    title: str
    description: str
    pages: int
    author: str
    publisher: str
    year: int

    class Config:
        from_attributes = True  # Pydantic v2 replacement for orm_mode

class BookCreate(BookBase):
    pass

class Book(BookBase):
    id: int

# --- Dummy users DB ---
fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "Rohit Narendra Chaudhari",
        "email": "rohit@example.com",
        "hashed_password": pwd_context.hash("password"),
        "disabled": False,
    }
}

# --- Dependency for DB session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Auth helpers ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(username: str):
    return fake_users_db.get(username)

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    return user

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    # Use username as token for simplicity
    return {"access_token": user["username"], "token_type": "bearer"}

async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = get_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user

# --- CRUD routes ---
@app.post("/books/", response_model=Book)
async def create_book(book: BookCreate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_book = BookDB(**book.dict())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book

@app.get("/books/", response_model=List[Book])
async def read_books(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(BookDB).all()

@app.delete("/books/{book_id}", status_code=204)
async def delete_book(book_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    book = db.query(BookDB).filter(BookDB.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete(book)
    db.commit()
    return

# --- Root route ---
@app.get("/")
async def root():
    return {"message": "Welcome to the Books API. Use /docs for API docs."}

# --- Add dummy data on startup ---
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    books_exist = db.query(BookDB).first()
    if not books_exist:
        dummy_books = [
            BookDB(title="Learn FastAPI", description="A complete guide to FastAPI", pages=300, author="admin", publisher="Omega Press", year=2025),
            BookDB(title="Python Basics", description="Introduction to Python", pages=250, author="admin", publisher="Omega Press", year=2024),
            BookDB(title="Advanced SQLAlchemy", description="Deep dive into SQLAlchemy ORM", pages=400, author="admin", publisher="Omega Press", year=2023),
        ]
        db.add_all(dummy_books)
        db.commit()
    db.close()
