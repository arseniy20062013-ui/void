# main.py
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator
import bcrypt
import jwt
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
import aiofiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ---------- Настройки ----------
DATABASE_URL = "sqlite:///./void.db"  # Для production заменить на PostgreSQL
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 дней
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Rate Limiter ----------
limiter = Limiter(key_func=get_remote_address)

# ---------- База данных ----------
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модели SQLAlchemy
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    nick = Column(String, unique=True, index=True, nullable=False)
    security_code = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    birth_date = Column(String, nullable=True)
    avatar = Column(String, nullable=True)
    role = Column(String, default="user")
    premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    agreed_to_terms = Column(Boolean, default=False)
    privacy = Column(JSON, default={
        "photo": "all", "photoExceptions": [],
        "status": "all", "statusExceptions": [],
        "lastSeen": "all", "lastSeenExceptions": [],
        "addToGroups": "all", "addToGroupsExceptions": [],
        "messages": "all", "messagesExceptions": []
    })
    custom_statuses = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    owned_chats = relationship("Chat", foreign_keys="Chat.owner_id", back_populates="owner")
    participants = relationship("Participant", back_populates="user")
    file_uploads = relationship("FileUpload", back_populates="user")

class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    nick = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    avatar = Column(String, nullable=True)
    type = Column(String)  # 'private', 'group', 'channel'
    is_public = Column(Boolean, default=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    link = Column(String, unique=True, nullable=True)
    pinned_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_chats")
    participants = relationship("Participant", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    pinned_message = relationship("Message", foreign_keys=[pinned_message_id])

class Participant(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    chat_id = Column(Integer, ForeignKey("chats.id"))
    joined = Column(Boolean, default=True)
    request_sent = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    pinned = Column(Boolean, default=False)
    blocked = Column(Boolean, default=False)
    last_read_message_id = Column(Integer, nullable=True)

    user = relationship("User", back_populates="participants")
    chat = relationship("Chat", back_populates="participants")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    content = Column(JSON)  # зашифрованное содержимое
    reply_to_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    forwarded = Column(Boolean, default=False)
    original_sender = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    replies = relationship("Message", backref="reply_to", remote_side=[id])

class FileUpload(Base):
    __tablename__ = "file_uploads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    filepath = Column(String)
    size = Column(Integer)
    mime_type = Column(String)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="file_uploads")

# Создание таблиц
Base.metadata.create_all(bind=engine)

# ---------- Схемы Pydantic ----------
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    name: str
    nick: str
    security_code: str
    password: str
    birth_date: Optional[str] = None

    @validator('nick')
    def validate_nick(cls, v):
        if not v.startswith('@'):
            v = '@' + v
        return v

class UserLogin(BaseModel):
    security_code: str
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    nick: str
    security_code: str
    birth_date: Optional[str]
    avatar: Optional[str]
    role: str
    premium: bool
    premium_until: Optional[datetime]
    custom_statuses: List[dict]
    privacy: dict

    class Config:
        orm_mode = True

class ChatCreate(BaseModel):
    name: str
    nick: str
    description: Optional[str] = ""
    type: str
    is_public: bool = True

class ChatOut(BaseModel):
    id: int
    name: str
    nick: str
    description: Optional[str]
    avatar: Optional[str]
    type: str
    is_public: bool
    link: Optional[str]
    participants_count: Optional[int] = 0
    joined: Optional[bool] = None
    request_sent: Optional[bool] = None
    pinned: Optional[bool] = None
    blocked: Optional[bool] = None

    class Config:
        orm_mode = True

class MessageIn(BaseModel):
    chat_id: int
    content: dict
    reply_to_id: Optional[int] = None
    forwarded: Optional[bool] = False
    original_sender: Optional[str] = None

class MessageOut(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    sender_nick: Optional[str]
    content: dict
    reply_to_id: Optional[int]
    forwarded: bool
    original_sender: Optional[str]
    timestamp: datetime
    edited_at: Optional[datetime]

    class Config:
        orm_mode = True

class PrivacySettingsUpdate(BaseModel):
    photo: str
    photoExceptions: List[str]
    status: str
    statusExceptions: List[str]
    lastSeen: str
    lastSeenExceptions: List[str]
    addToGroups: str
    addToGroupsExceptions: List[str]
    messages: str
    messagesExceptions: List[str]

class StatusUpdate(BaseModel):
    custom_statuses: List[dict]

# ---------- Зависимости ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ---------- Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старте можно выполнить дополнительные действия
    yield

# ---------- Приложение ----------
app = FastAPI(title="VOID API", version="0.1", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://void_official.com", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Статические файлы
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ---------- Эндпоинты ----------
@app.post("/api/register", response_model=Token)
@limiter.limit("5/minute")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.nick == user.nick).first():
        raise HTTPException(status_code=400, detail="Nick already taken")
    if db.query(User).filter(User.security_code == user.security_code).first():
        raise HTTPException(status_code=400, detail="Security code already used")
    hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()
    new_user = User(
        name=user.name,
        nick=user.nick,
        security_code=user.security_code,
        password_hash=hashed,
        birth_date=user.birth_date
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    access_token = jwt.encode(
        {"sub": new_user.id, "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
        SECRET_KEY, algorithm=ALGORITHM
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/login", response_model=Token)
@limiter.limit("10/minute")
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.security_code == user_data.security_code).first()
    if not user or not bcrypt.checkpw(user_data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = jwt.encode(
        {"sub": user.id, "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
        SECRET_KEY, algorithm=ALGORITHM
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.put("/api/me/profile", response_model=UserOut)
async def update_profile(
    name: Optional[str] = Form(None),
    nick: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if name:
        current_user.name = name
    if nick:
        if nick != current_user.nick and db.query(User).filter(User.nick == nick).first():
            raise HTTPException(status_code=400, detail="Nick already taken")
        current_user.nick = nick
    if birth_date:
        current_user.birth_date = birth_date
    if avatar:
        ext = os.path.splitext(avatar.filename)[1]
        filename = f"avatar_{current_user.id}_{uuid.uuid4()}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        async with aiofiles.open(filepath, 'wb') as f:
            content = await avatar.read()
            await f.write(content)
        if current_user.avatar:
            old_path = os.path.join(UPLOAD_DIR, current_user.avatar.replace("/uploads/", ""))
            if os.path.exists(old_path):
                os.remove(old_path)
        current_user.avatar = f"/uploads/{filename}"
    db.commit()
    db.refresh(current_user)
    return current_user

@app.put("/api/me/privacy", response_model=UserOut)
async def update_privacy(settings: PrivacySettingsUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.privacy = settings.dict()
    db.commit()
    db.refresh(current_user)
    return current_user

@app.put("/api/me/statuses", response_model=UserOut)
async def update_statuses(statuses: StatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.premium and len(statuses.custom_statuses) > 2:
        raise HTTPException(status_code=400, detail="Non-premium users can have at most 2 statuses")
    current_user.custom_statuses = statuses.custom_statuses
    db.commit()
    db.refresh(current_user)
    return current_user

@app.post("/api/me/premium")
async def purchase_premium(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.premium:
        raise HTTPException(status_code=400, detail="Already premium")
    current_user.premium = True
    current_user.premium_until = datetime.utcnow() + timedelta(days=30)
    db.commit()
    return {"status": "success", "premium_until": current_user.premium_until}

@app.get("/api/users/search")
async def search_users(q: str = Query(..., min_length=1), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).filter(
        (User.name.ilike(f"%{q}%")) | (User.nick.ilike(f"%{q}%")) | (User.security_code.ilike(f"%{q}%"))
    ).limit(20).all()
    return [{"id": u.id, "name": u.name, "nick": u.nick, "avatar": u.avatar} for u in users if u.id != current_user.id]

@app.get("/api/chats", response_model=List[ChatOut])
async def get_my_chats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    participants = db.query(Participant).filter(Participant.user_id == current_user.id, Participant.blocked == False).all()
    result = []
    for p in participants:
        chat = p.chat
        if chat:
            out = ChatOut.from_orm(chat)
            out.participants_count = db.query(Participant).filter(Participant.chat_id == chat.id).count()
            out.joined = p.joined
            out.request_sent = p.request_sent
            out.pinned = p.pinned
            out.blocked = p.blocked
            result.append(out)
    return sorted(result, key=lambda x: (not x.pinned, x.name))

@app.post("/api/chats", response_model=ChatOut)
async def create_chat(chat_data: ChatCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.query(Chat).filter(Chat.nick == chat_data.nick).first():
        raise HTTPException(status_code=400, detail="Nick already used")
    new_chat = Chat(
        name=chat_data.name,
        nick=chat_data.nick,
        description=chat_data.description,
        type=chat_data.type,
        is_public=chat_data.is_public,
        owner_id=current_user.id,
        link=f"https://void_official.com/{chat_data.nick[1:]}" if chat_data.is_public else None
    )
    db.add(new_chat)
    db.flush()
    participant = Participant(user_id=current_user.id, chat_id=new_chat.id, joined=True, is_admin=True)
    db.add(participant)
    db.commit()
    db.refresh(new_chat)
    return new_chat

@app.get("/api/chats/{chat_id}", response_model=ChatOut)
async def get_chat(chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    participant = db.query(Participant).filter(Participant.chat_id == chat_id, Participant.user_id == current_user.id).first()
    out = ChatOut.from_orm(chat)
    out.participants_count = db.query(Participant).filter(Participant.chat_id == chat_id).count()
    if participant:
        out.joined = participant.joined
        out.request_sent = participant.request_sent
        out.pinned = participant.pinned
        out.blocked = participant.blocked
    else:
        out.joined = False
    return out

@app.post("/api/chats/{chat_id}/join")
async def join_chat(chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    participant = db.query(Participant).filter(Participant.chat_id == chat_id, Participant.user_id == current_user.id).first()
    if participant:
        if participant.joined:
            raise HTTPException(status_code=400, detail="Already joined")
        participant.joined = True
        participant.request_sent = False
    else:
        if not chat.is_public:
            participant = Participant(user_id=current_user.id, chat_id=chat_id, request_sent=True, joined=False)
        else:
            participant = Participant(user_id=current_user.id, chat_id=chat_id, joined=True)
        db.add(participant)
    db.commit()
    return {"status": "success"}

@app.post("/api/chats/{chat_id}/leave")
async def leave_chat(chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    participant = db.query(Participant).filter(Participant.chat_id == chat_id, Participant.user_id == current_user.id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Not a participant")
    db.delete(participant)
    db.commit()
    return {"status": "left"}

@app.patch("/api/chats/{chat_id}/pin")
async def pin_chat(chat_id: int, pin: bool = True, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    participant = db.query(Participant).filter(Participant.chat_id == chat_id, Participant.user_id == current_user.id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Not a participant")
    participant.pinned = pin
    db.commit()
    return {"pinned": pin}

@app.patch("/api/chats/{chat_id}/block")
async def block_chat(chat_id: int, block: bool = True, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    participant = db.query(Participant).filter(Participant.chat_id == chat_id, Participant.user_id == current_user.id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Not a participant")
    participant.blocked = block
    db.commit()
    return {"blocked": block}

@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete")
    db.delete(chat)
    db.commit()
    return {"status": "deleted"}

@app.get("/api/chats/{chat_id}/messages", response_model=List[MessageOut])
async def get_messages(chat_id: int, limit: int = 50, before: Optional[int] = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    participant = db.query(Participant).filter(Participant.chat_id == chat_id, Participant.user_id == current_user.id).first()
    if not participant or not participant.joined:
        raise HTTPException(status_code=403, detail="You are not a member of this chat")
    query = db.query(Message).filter(Message.chat_id == chat_id, Message.deleted_at == None)
    if before:
        query = query.filter(Message.id < before)
    messages = query.order_by(Message.timestamp.desc()).limit(limit).all()
    result = []
    for m in messages:
        out = MessageOut.from_orm(m)
        sender = db.query(User).filter(User.id == m.sender_id).first()
        out.sender_nick = sender.nick if sender else None
        result.append(out)
    return result[::-1]

@app.post("/api/messages", response_model=MessageOut)
async def send_message(message: MessageIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    participant = db.query(Participant).filter(Participant.chat_id == message.chat_id, Participant.user_id == current_user.id).first()
    if not participant or not participant.joined:
        raise HTTPException(status_code=403, detail="You are not a member of this chat")
    new_msg = Message(
        chat_id=message.chat_id,
        sender_id=current_user.id,
        content=message.content,
        reply_to_id=message.reply_to_id,
        forwarded=message.forwarded,
        original_sender=message.original_sender
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    out = MessageOut.from_orm(new_msg)
    out.sender_nick = current_user.nick
    return out

@app.delete("/api/messages/{message_id}")
async def delete_message(message_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Can only delete own messages")
    msg.deleted_at = datetime.utcnow()
    db.commit()
    return {"status": "deleted"}

@app.patch("/api/messages/{message_id}/pin")
async def pin_message(message_id: int, chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    participant = db.query(Participant).filter(Participant.chat_id == chat_id, Participant.user_id == current_user.id).first()
    if not participant or not (participant.is_admin or chat.owner_id == current_user.id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if chat.pinned_message_id == message_id:
        chat.pinned_message_id = None
    else:
        chat.pinned_message_id = message_id
    db.commit()
    return {"pinned_message_id": chat.pinned_message_id}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1]
    filename = f"file_{current_user.id}_{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    size = 0
    async with aiofiles.open(filepath, 'wb') as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            await f.write(chunk)
    file_record = FileUpload(
        user_id=current_user.id,
        filename=file.filename,
        filepath=f"/uploads/{filename}",
        size=size,
        mime_type=file.content_type
    )
    db.add(file_record)
    db.commit()
    return {"url": f"/uploads/{filename}", "name": file.filename, "size": size}

@app.get("/api/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/api/users/by-nick/{nick}", response_model=UserOut)
async def get_user_by_nick(nick: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not nick.startswith('@'):
        nick = '@' + nick
    user = db.query(User).filter(User.nick == nick).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
