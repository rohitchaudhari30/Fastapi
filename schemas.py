from pydantic import BaseModel

class BookCreate(BaseModel):
    title: str
    description: str
    pages: int
    author: str
    publisher: str
    year: int




class BookOut(BookCreate):
    id: int

    class Config:
        from_attributes = True  # for Pydantic v2 compatibility

class Token(BaseModel):
    access_token: str
    token_type: str
