from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import ForeignKey
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__="users"
    id: Mapped[int]= mapped_column(primary_key=True)
    username: Mapped[str]= mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]= mapped_column()
    created_at: Mapped[datetime]= mapped_column(default=datetime.now)
    
class APIKey(Base):
    __tablename__="api_keys"
    id : Mapped[int]= mapped_column(primary_key=True)
    key_value: Mapped[str] = mapped_column(unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_active: Mapped[bool]=mapped_column(default=True)
    quota_limit: Mapped[int] = mapped_column(default=True)
    
     
    
    