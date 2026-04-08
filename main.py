import subprocess
import asyncio
import os
import io
from datetime import datetime, timedelta
from typing import List

import pyotp
import qrcode
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt

from database import SessionLocal, User, Game

# ---------- Конфигурация ----------
app = FastAPI(title="Game Collector", description="Коллекционное приложение для игр с 2FA")
load_dotenv()
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "supersecretkeychangeme"   # замените на случайный в .env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
TEMP_TOKEN_EXPIRE_MINUTES = 5

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()

# ---------- Зависимость БД ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------- Pydantic модели ----------
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
    twofa_required: bool = False

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

class TwoFactorCode(BaseModel):
    code: str

class TwoFactorLogin(BaseModel):
    temp_token: str
    code: str

# ---------- Вспомогательные функции ----------
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
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                           db: Session = Depends(get_db)) -> User:
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

# ---------- Функция-заглушка для рекомендаций ----------
async def get_recommendations_stub(genres: List[str]) -> List[GameRecommendation]:
    # Если нет жанров, возвращаем пустой список
    if not genres:
        return []

    # Формируем строку жанров, разделённых запятыми
    genres_str = ",".join(genres).lower()
    
    # Путь к исполняемому файлу C++ модуля
    cpp_program = "./cpp_module/recommend.exe"

    # Проверяем, существует ли файл
    if not os.path.exists(cpp_program):
        print(f"Ошибка: Модуль рекомендаций не найден по пути {cpp_program}")
        return []

    try:
        # Запускаем C++ программу асинхронно
        process = await asyncio.create_subprocess_exec(
            cpp_program, genres_str, RAWG_API_KEY,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            print(f"Ошибка выполнения C++ модуля: {stderr.decode('utf-8')}")
            return []

        # Парсим вывод программы
        output = stdout.decode('utf-8').strip()
        recommended_games = []
        for line in output.split('\n'):
            if '|' not in line:
                continue
            try:
                game_id_str, game_name = line.split('|', 1)
                recommended_games.append(GameRecommendation(name=game_name, genre="рекомендация"))
            except ValueError:
                continue

        # Возвращаем первые 5 результатов
        return recommended_games[:5]

    except Exception as e:
        print(f"Ошибка при вызове C++ модуля: {e}")
        return []

# ---------- Эндпоинты ----------

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
    if db_user.is_2fa_enabled:
        temp_data = {"sub": db_user.username, "2fa_pending": True}
        temp_token = create_access_token(temp_data, expires_delta=timedelta(minutes=TEMP_TOKEN_EXPIRE_MINUTES))
        return Token(access_token=temp_token, token_type="bearer", twofa_required=True)
    else:
        access_token = create_access_token(data={"sub": db_user.username})
        return Token(access_token=access_token, token_type="bearer", twofa_required=False)

@app.post("/login-2fa", response_model=Token)
async def login_2fa(data: TwoFactorLogin, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Неверный или истёкший временный токен")
    try:
        payload = jwt.decode(data.temp_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        pending = payload.get("2fa_pending")
        if not username or not pending:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_2fa_enabled or not user.totp_secret:
        raise credentials_exception
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(data.code):
        raise HTTPException(status_code=400, detail="Неверный код 2FA")
    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token, token_type="bearer", twofa_required=False)

@app.post("/enable-2fa")
async def enable_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA уже включена")
    if not current_user.totp_secret:
        secret = pyotp.random_base32()
        current_user.totp_secret = secret
        db.commit()
    else:
        secret = current_user.totp_secret
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=current_user.username, issuer_name="GameCollector")
    # Генерация QR-кода
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")

@app.get("/get-2fa-secret")
async def get_2fa_secret(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.totp_secret:
        raise HTTPException(status_code=404, detail="Секрет не сгенерирован. Сначала вызовите POST /enable-2fa")
    return {"secret": current_user.totp_secret}

@app.post("/verify-2fa")
async def verify_2fa(code_data: TwoFactorCode, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA не настроена. Сначала вызовите /enable-2fa")
    if current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA уже активирована")
    totp = pyotp.TOTP(current_user.totp_secret)
    if totp.verify(code_data.code):
        current_user.is_2fa_enabled = 1
        db.commit()
        return {"message": "2FA успешно активирована"}
    else:
        raise HTTPException(status_code=400, detail="Неверный код")

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
    user_games = db.query(Game).filter(Game.owner_id == current_user.id).all()
    if not user_games:
        raise HTTPException(status_code=404, detail="Ваша коллекция пуста. Добавьте хотя бы одну игру.")
    genres = list(set([g.genre for g in user_games if g.genre]))
    if not genres:
        raise HTTPException(status_code=404, detail="В ваших играх не указаны жанры.")
    loop = asyncio.get_event_loop()
    recommendations_list = await loop.run_in_executor(None, lambda: asyncio.run(get_recommendations_stub(genres)))
    return recommendations_list

# ---------- Статика ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")