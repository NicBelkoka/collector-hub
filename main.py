import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt

from database import SessionLocal, User, Game

# ---------- Конфигурация приложения ----------
app = FastAPI(title="Game Collector", description="Коллекционное приложение для игр с рекомендациями")

# Разрешаем CORS для разработки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Настройки безопасности ----------
SECRET_KEY = "supersecretkeychangeme"   # в реальном проекте хранить в .env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Хеширование паролей через pbkdf2_sha256 (не требует bcrypt)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Схема для получения Bearer токена
security = HTTPBearer()

# ---------- Зависимость для получения сессии БД ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------- Pydantic модели (схемы данных) ----------
class UserCreate(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class GameCreate(BaseModel):
    title: str
    genre: str

class GameOut(BaseModel):
    id: int
    title: str
    genre: str
    owner_id: int
    class Config:
        from_attributes = True

class GameRecommendation(BaseModel):
    name: str
    genre: str

# ---------- Вспомогательные функции для аутентификации ----------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# ---------- Функция-заглушка для рекомендаций (асинхронная) ----------
async def get_recommendations_stub(genres: List[str]) -> List[GameRecommendation]:
    """
    Заглушка, имитирующая обращение к внешнему сервису или C++ модулю.
    Позже вы замените на реальный вызов.
    """
    # Имитация долгой работы (1 секунда), чтобы показать асинхронность
    await asyncio.sleep(1)

    # База популярных игр по жанрам (для примера)
    game_db = {
        "rpg": ["Ведьмак 3", "Elden Ring", "Baldur's Gate 3", "Skyrim", "Final Fantasy VII"],
        "action": ["Doom Eternal", "Dark Souls", "Sekiro", "Hades", "Devil May Cry 5"],
        "adventure": ["The Legend of Zelda", "God of War", "Uncharted 4", "Tomb Raider", "Horizon Zero Dawn"],
        "strategy": ["Civilization VI", "StarCraft II", "Total War: Warhammer", "Age of Empires IV", "XCOM 2"],
        "sports": ["FIFA 23", "NBA 2K24", "Madden NFL 24", "Rocket League", "Tony Hawk's Pro Skater"],
    }

    recommendations = []
    for genre in genres:
        genre_lower = genre.lower()
        if genre_lower in game_db:
            for game in game_db[genre_lower]:
                if not any(rec.name == game for rec in recommendations):
                    recommendations.append(GameRecommendation(name=game, genre=genre))
            if len(recommendations) >= 5:
                break
    # Если набрали меньше 5, добавим популярные игры по умолчанию
    default_games = ["Portal 2", "Minecraft", "Stardew Valley", "Celeste", "Hollow Knight"]
    for game in default_games:
        if len(recommendations) >= 5:
            break
        if not any(rec.name == game for rec in recommendations):
            recommendations.append(GameRecommendation(name=game, genre="популярное"))
    return recommendations[:5]

# ---------- Эндпоинты API ----------

@app.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
    hashed = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login", response_model=Token)
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = authenticate_user(db, user.username, user.password)
    if not db_user:
        raise HTTPException(status_code=400, detail="Неверное имя пользователя или пароль")
    access_token = create_access_token(data={"sub": db_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/games", response_model=GameOut)
def add_game(game: GameCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_game = Game(title=game.title, genre=game.genre, owner_id=current_user.id)
    db.add(db_game)
    db.commit()
    db.refresh(db_game)
    return db_game

@app.get("/games", response_model=List[GameOut])
def list_games(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    games = db.query(Game).filter(Game.owner_id == current_user.id).all()
    return games

@app.get("/recommendations", response_model=List[GameRecommendation])
async def recommendations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Получаем все игры пользователя
    user_games = db.query(Game).filter(Game.owner_id == current_user.id).all()
    if not user_games:
        raise HTTPException(status_code=404, detail="Ваша коллекция пуста. Добавьте хотя бы одну игру.")
    genres = list(set([g.genre for g in user_games if g.genre]))
    if not genres:
        raise HTTPException(status_code=404, detail="В ваших играх не указаны жанры.")

    # Асинхронный вызов функции-заглушки (демонстрация многопоточности)
    loop = asyncio.get_event_loop()
    recommendations_list = await loop.run_in_executor(None, lambda: asyncio.run(get_recommendations_stub(genres)))
    return recommendations_list

# ---------- Раздача статических файлов (фронтенд) ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")