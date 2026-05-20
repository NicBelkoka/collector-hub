import os
import asyncio
import subprocess
import io
from datetime import datetime, timedelta
from typing import List, Optional

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
import pyotp
import qrcode

from database import SessionLocal, User, Game

load_dotenv()
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
if not RAWG_API_KEY:
    print("WARNING: RAWG_API_KEY not set")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "supersecretkeychangeme"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
TEMP_TOKEN_EXPIRE_MINUTES = 5

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
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
    external_id: Optional[int] = None

class GameOut(BaseModel):
    id: int
    title: str
    genre: str
    owner_id: int
    external_id: Optional[int] = None
    class Config:
        from_attributes = True

class GameRecommendation(BaseModel):
    id: int
    name: str
    genre: str

class TwoFactorCode(BaseModel):
    code: str

class TwoFactorLogin(BaseModel):
    temp_token: str
    code: str

# Auth helpers
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                           db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ---------- 2FA endpoints ----------
@app.post("/enable-2fa")
async def enable_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA already enabled")
    if not current_user.totp_secret:
        current_user.totp_secret = pyotp.random_base32()
        db.commit()
    totp = pyotp.TOTP(current_user.totp_secret)
    uri = totp.provisioning_uri(name=current_user.username, issuer_name="GameCollector")
    qr = qrcode.make(uri)
    img_byte_arr = io.BytesIO()
    qr.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")

@app.get("/get-2fa-secret")
async def get_2fa_secret(current_user: User = Depends(get_current_user)):
    if not current_user.totp_secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    return {"secret": current_user.totp_secret}

@app.post("/verify-2fa")
async def verify_2fa(code_data: TwoFactorCode, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.totp_secret or current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA not configured or already enabled")
    totp = pyotp.TOTP(current_user.totp_secret)
    if totp.verify(code_data.code):
        current_user.is_2fa_enabled = 1
        db.commit()
        return {"message": "2FA activated"}
    else:
        raise HTTPException(status_code=400, detail="Invalid code")

@app.get("/user/2fa-status")
async def get_2fa_status(current_user: User = Depends(get_current_user)):
    return {"enabled": bool(current_user.is_2fa_enabled)}

# Auth endpoints
@app.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
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
        raise HTTPException(status_code=400, detail="Invalid credentials")
    if db_user.is_2fa_enabled:
        temp_token = create_access_token({"sub": db_user.username, "2fa_pending": True},
                                         timedelta(minutes=TEMP_TOKEN_EXPIRE_MINUTES))
        return Token(access_token=temp_token, token_type="bearer", twofa_required=True)
    else:
        access_token = create_access_token({"sub": db_user.username})
        return Token(access_token=access_token, token_type="bearer", twofa_required=False)

@app.post("/login-2fa", response_model=Token)
async def login_2fa(data: TwoFactorLogin, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(data.temp_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        pending = payload.get("2fa_pending")
        if not username or not pending:
            raise HTTPException(status_code=401, detail="Invalid temp token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid temp token")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_2fa_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="2FA not set up")
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(data.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")
    access_token = create_access_token({"sub": user.username})
    return Token(access_token=access_token, token_type="bearer", twofa_required=False)

# Games endpoints
@app.post("/games", response_model=GameOut)
def add_game(game: GameCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_game = Game(
        title=game.title,
        genre=game.genre,
        external_id=game.external_id,
        owner_id=current_user.id
    )
    db.add(db_game)
    db.commit()
    db.refresh(db_game)
    return db_game

@app.delete("/games/{game_id}")
def delete_game(game_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.id == game_id, Game.owner_id == current_user.id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Игра не найдена")
    db.delete(game)
    db.commit()
    return {"message": "Игра удалена"}

@app.get("/games", response_model=List[GameOut])
def list_games(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Game).filter(Game.owner_id == current_user.id).all()

# ---------- Recommendations via C++ module (by genres) ----------
async def get_recommendations_from_cpp(genres_str: str) -> List[GameRecommendation]:
    if not RAWG_API_KEY:
        print("[DEBUG] No API key")
        return []
    cpp_program = "./cpp_module/recommend.exe"
    abs_path = os.path.abspath(cpp_program)
    print(f"[DEBUG] Full path to C++ module: {abs_path}")
    if not os.path.exists(abs_path):
        print(f"[DEBUG] Module not found at {abs_path}")
        return []
    print(f"[DEBUG] Calling C++ with genres: {genres_str}")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [abs_path, genres_str, RAWG_API_KEY],
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8'
            )
        )
        print(f"[DEBUG] Return code: {result.returncode}")
        if result.stderr:
            print(f"[DEBUG] STDERR: {result.stderr.strip()}")
        output = result.stdout.strip()
        print(f"[DEBUG] STDOUT length: {len(output)}")
        if not output:
            print("[DEBUG] Empty output")
            return []
        games = []
        for line in output.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|')
            if len(parts) >= 3:
                try:
                    game_id = int(parts[0])
                    name = parts[1]
                    genre = parts[2]
                    games.append(GameRecommendation(id=game_id, name=name, genre=genre))
                except Exception as e:
                    print(f"[DEBUG] Parse error: {e} on line '{line}'")
        print(f"[DEBUG] Parsed {len(games)} games")
        return games
    except subprocess.TimeoutExpired:
        print("[DEBUG] Timeout")
        return []
    except Exception as e:
        print(f"[DEBUG] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.get("/recommendations", response_model=List[GameRecommendation])
async def recommendations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_games = db.query(Game).filter(Game.owner_id == current_user.id).all()
    if not user_games:
        # Коллекция пуста — возвращаем популярные игры
        popular = await get_recommendations_from_cpp("popular")
        return popular[:5]

    # Собираем уникальные жанры (преобразуем в slugs для RAWG)
    genres_set = set()
    genre_map = {
        "ролевая": "rpg", "ролевые": "rpg", "rpg": "rpg",
        "экшен": "action", "action": "action",
        "шутер": "shooter", "shooter": "shooter",
        "стратегия": "strategy", "strategy": "strategy",
        "приключение": "adventure", "adventure": "adventure",
        "симулятор": "simulation", "simulation": "simulation",
        "инди": "indie", "indie": "indie"
    }
    for g in user_games:
        if g.genre:
            slug = genre_map.get(g.genre.lower(), g.genre.lower())
            genres_set.add(slug)
    if not genres_set:
        popular = await get_recommendations_from_cpp("")
        return popular[:5]

    genres_str = ",".join(genres_set)
    raw_recs = await get_recommendations_from_cpp(genres_str)
    existing_ids = {g.external_id for g in user_games if g.external_id}
    filtered = [g for g in raw_recs if g.id not in existing_ids]

    # Если после фильтрации ничего не осталось — берём популярные игры
    if not filtered:
        popular = await get_recommendations_from_cpp("popular")
        return popular[:5]

    return filtered[:5]

# Serve static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")