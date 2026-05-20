# Импорт модуля для работы с операционной системой (файлы, пути, переменные окружения)
import os
# Импорт модуля для асинхронного программирования (async/await)
import asyncio
# Импорт модуля для запуска внешних процессов (вызов C++ программы)
import subprocess
# Импорт модуля для работы с потоками ввода-вывода (бинарные данные)
import io
# Импорт классов для работы с датой и временем из модуля datetime
from datetime import datetime, timedelta
# Импорт типов List (список) и Optional (возможное отсутствие значения)
from typing import List, Optional

# Импорт функции для загрузки переменных из .env файла
from dotenv import load_dotenv
# Импорт FastAPI и зависимостей для создания API
from fastapi import FastAPI, Depends, HTTPException, status
# Импорт middleware для обработки CORS (кросс-доменные запросы)
from fastapi.middleware.cors import CORSMiddleware
# Импорт классов для HTTP Bearer аутентификации
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# Импорт для раздачи статических файлов (HTML, CSS, JS)
from fastapi.staticfiles import StaticFiles
# Импорт StreamingResponse для отправки потоковых данных (например, QR-код)
from fastapi.responses import StreamingResponse
# Импорт сессии и моделей SQLAlchemy из локального модуля database
from sqlalchemy.orm import Session
# Импорт базовых Pydantic моделей для валидации данных
from pydantic import BaseModel
# Импорт контекста для хеширования паролей (PBKDF2)
from passlib.context import CryptContext
# Импорт функций для работы с JWT токенами
from jose import JWTError, jwt
# Импорт модуля для TOTP (2FA) генерации и проверки кодов
import pyotp
# Импорт модуля для генерации QR-кодов
import qrcode

# Импорт базы данных и моделей из локального файла database.py
from database import SessionLocal, User, Game

# Загружаем переменные окружения из .env файла
load_dotenv()
# Получаем API ключ для RAWG (сервис игр) из переменных окружения
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
# Проверяем, установлен ли ключ, если нет - выводим предупреждение
if not RAWG_API_KEY:
    print("WARNING: RAWG_API_KEY not set")

# Создаем экземпляр FastAPI приложения
app = FastAPI()
# Добавляем middleware для обработки CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем запросы с любых доменов
    allow_credentials=True,  # Разрешаем отправку cookies/credentials
    allow_methods=["*"],  # Разрешаем все HTTP методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

# Секретный ключ для подписи JWT (в реальном проекте нужно в .env)
SECRET_KEY = "supersecretkeychangeme"
# Алгоритм шифрования JWT
ALGORITHM = "HS256"
# Время жизни обычного токена доступа (30 минут)
ACCESS_TOKEN_EXPIRE_MINUTES = 30
# Время жизни временного токена для 2FA (5 минут)
TEMP_TOKEN_EXPIRE_MINUTES = 5

# Создаем контекст для хеширования паролей с алгоритмом PBKDF2-SHA256
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
# Создаем объект для извлечения Bearer токена из заголовка Authorization
security = HTTPBearer()

# Функция-генератор для получения сессии базы данных
def get_db():
    # Создаем новую сессию
    db = SessionLocal()
    try:
        # Возвращаем сессию для использования в зависимостях
        yield db
    finally:
        # Закрываем сессию после завершения запроса
        db.close()

# Pydantic модели для валидации данных

# Модель для создания нового пользователя
class UserCreate(BaseModel):
    username: str  # Имя пользователя (строка)
    password: str  # Пароль (строка)

# Модель для ответа с данными пользователя (без пароля)
class UserOut(BaseModel):
    id: int  # ID пользователя
    username: str  # Имя пользователя
    class Config:
        from_attributes = True  # Разрешаем создание из SQLAlchemy модели (вместо orm_mode)

# Модель для ответа с токеном
class Token(BaseModel):
    access_token: str  # Сам JWT токен
    token_type: str  # Тип токена (обычно "bearer")
    twofa_required: bool = False  # Флаг, требуется ли двухфакторная аутентификация

# Модель для создания новой игры
class GameCreate(BaseModel):
    title: str  # Название игры
    genre: str  # Жанр игры
    external_id: Optional[int] = None  # Внешний ID из RAWG API (может отсутствовать)

# Модель для ответа с данными игры
class GameOut(BaseModel):
    id: int  # Локальный ID игры
    title: str  # Название игры
    genre: str  # Жанр игры
    owner_id: int  # ID владельца коллекции
    external_id: Optional[int] = None  # Внешний ID из RAWG API
    class Config:
        from_attributes = True  # Поддержка SQLAlchemy моделей

# Модель для рекомендации игры
class GameRecommendation(BaseModel):
    id: int  # ID игры в RAWG
    name: str  # Название игры
    genre: str  # Жанр игры

# Модель для получения кода 2FA
class TwoFactorCode(BaseModel):
    code: str  # 6-значный код из TOTP приложения

# Модель для завершения входа с 2FA
class TwoFactorLogin(BaseModel):
    temp_token: str  # Временный токен, полученный при первом входе
    code: str  # 2FA код

# Вспомогательные функции аутентификации

# Функция проверки пароля (сравнение plain с хешем)
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)  # passlib проверяет пароль

# Функция хеширования пароля
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)  # Возвращает хеш для хранения в БД

# Функция аутентификации пользователя по username и паролю
def authenticate_user(db: Session, username: str, password: str):
    # Ищем пользователя в БД
    user = db.query(User).filter(User.username == username).first()
    # Если пользователь не найден или пароль неверен - возвращаем None
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user  # Возвращаем объект пользователя

# Функция создания JWT токена
def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()  # Копируем данные для токена
    # Устанавливаем время истечения токена
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})  # Добавляем время истечения в payload
    # Кодируем JWT с секретным ключом
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Функция получения текущего пользователя из токена (зависимость FastAPI)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                           db: Session = Depends(get_db)) -> User:
    token = credentials.credentials  # Извлекаем токен из заголовка
    try:
        # Декодируем JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")  # Извлекаем имя пользователя
        if not username:
            raise HTTPException(status_code=401, detail="Недействительный токен")
    except JWTError:  # Ошибка при декодировании
        raise HTTPException(status_code=401, detail="Недействительный токен")
    # Ищем пользователя в БД
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user  # Возвращаем авторизованного пользователя

# ---------- 2FA endpoints ----------

# Эндпоинт для включения 2FA (возвращает QR-код)
@app.post("/enable-2fa")
async def enable_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Проверяем, не включена ли уже 2FA
    if current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA уже включена")
    # Если секрет отсутствует - генерируем новый
    if not current_user.totp_secret:
        current_user.totp_secret = pyotp.random_base32()  # Генерация случайного секрета
        db.commit()  # Сохраняем в БД
    # Создаем TOTP объект
    totp = pyotp.TOTP(current_user.totp_secret)
    # Генерируем URI для QR-кода
    uri = totp.provisioning_uri(name=current_user.username, issuer_name="GameCollector")
    # Создаем QR-код
    qr = qrcode.make(uri)
    # Создаем байтовый буфер для PNG изображения
    img_byte_arr = io.BytesIO()
    qr.save(img_byte_arr, format='PNG')  # Сохраняем PNG в буфер
    img_byte_arr.seek(0)  # Перемещаем указатель в начало буфера
    # Возвращаем изображение как поток
    return StreamingResponse(img_byte_arr, media_type="image/png")

# Эндпоинт для получения секрета 2FA (для отладки)
@app.get("/get-2fa-secret")
async def get_2fa_secret(current_user: User = Depends(get_current_user)):
    if not current_user.totp_secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    return {"secret": current_user.totp_secret}  # Возвращаем секрет в JSON

# Эндпоинт для подтверждения и активации 2FA
@app.post("/verify-2fa")
async def verify_2fa(code_data: TwoFactorCode, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Проверяем, что 2FA еще не активирована и секрет существует
    if not current_user.totp_secret or current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA не настроена или уже включена")
    totp = pyotp.TOTP(current_user.totp_secret)
    # Проверяем введенный код
    if totp.verify(code_data.code):
        current_user.is_2fa_enabled = 1  # Активируем 2FA в БД (1 = True)
        db.commit()  # Сохраняем изменения
        return {"message": "2FA activated"}
    else:
        raise HTTPException(status_code=400, detail="Неверный код")

# Эндпоинт для получения статуса 2FA пользователя
@app.get("/user/2fa-status")
async def get_2fa_status(current_user: User = Depends(get_current_user)):
    return {"enabled": bool(current_user.is_2fa_enabled)}  # Возвращаем булево значение

# Auth endpoints

# Эндпоинт регистрации нового пользователя
@app.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Проверяем, не занято ли имя пользователя
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    # Хешируем пароль
    hashed = get_password_hash(user.password)
    # Создаем нового пользователя
    new_user = User(username=user.username, hashed_password=hashed)
    db.add(new_user)  # Добавляем в сессию
    db.commit()  # Сохраняем в БД
    db.refresh(new_user)  # Обновляем объект из БД (получаем ID)
    return new_user

# Эндпоинт для первого этапа входа (проверка пароля)
@app.post("/login", response_model=Token)
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = authenticate_user(db, user.username, user.password)
    if not db_user:
        raise HTTPException(status_code=400, detail="Неверное имя пользователя или пароль")
    # Если включена 2FA - выдаем временный токен
    if db_user.is_2fa_enabled:
        temp_token = create_access_token({"sub": db_user.username, "2fa_pending": True},
                                         timedelta(minutes=TEMP_TOKEN_EXPIRE_MINUTES))
        return Token(access_token=temp_token, token_type="bearer", twofa_required=True)
    else:
        # Если 2FA не включена - выдаем обычный токен
        access_token = create_access_token({"sub": db_user.username})
        return Token(access_token=access_token, token_type="bearer", twofa_required=False)

# Эндпоинт для завершения входа с 2FA кодом
@app.post("/login-2fa", response_model=Token)
async def login_2fa(data: TwoFactorLogin, db: Session = Depends(get_db)):
    try:
        # Декодируем временный токен
        payload = jwt.decode(data.temp_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        pending = payload.get("2fa_pending")
        # Проверяем наличие флага 2fa_pending
        if not username or not pending:
            raise HTTPException(status_code=401, detail="Invalid temp token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid temp token")
    # Находим пользователя в БД
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_2fa_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="2FA не настроена")
    # Проверяем 2FA код
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(data.code):
        raise HTTPException(status_code=400, detail="2FA неверный код")
    # Выдаем постоянный токен
    access_token = create_access_token({"sub": user.username})
    return Token(access_token=access_token, token_type="bearer", twofa_required=False)

# Games endpoints

# Эндпоинт для добавления игры в коллекцию
@app.post("/games", response_model=GameOut)
def add_game(game: GameCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Создаем объект игры
    db_game = Game(
        title=game.title,
        genre=game.genre,
        external_id=game.external_id,
        owner_id=current_user.id
    )
    db.add(db_game)  # Добавляем в сессию
    db.commit()  # Сохраняем в БД
    db.refresh(db_game)  # Обновляем объект
    return db_game

# Эндпоинт для удаления игры из коллекции
@app.delete("/games/{game_id}")
def delete_game(game_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Ищем игру, принадлежащую текущему пользователю
    game = db.query(Game).filter(Game.id == game_id, Game.owner_id == current_user.id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Игра не найдена")  # Ошибка на русском
    db.delete(game)  # Удаляем объект из сессии
    db.commit()  # Сохраняем изменения
    return {"message": "Игра удалена"}  # Успешный ответ

# Эндпоинт для получения списка игр пользователя
@app.get("/games", response_model=List[GameOut])
def list_games(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Возвращаем все игры текущего пользователя
    return db.query(Game).filter(Game.owner_id == current_user.id).all()

# ---------- Recommendations via C++ module (by genres) ----------

# Асинхронная функция получения рекомендаций через C++ модуль
async def get_recommendations_from_cpp(genres_str: str, page: int = 1) -> List[GameRecommendation]:
    if not RAWG_API_KEY:
        return []  # Если нет API ключа - возвращаем пустой список
    # Путь к исполняемому файлу C++ программы
    cpp_program = "./cpp_module/recommend.exe"
    if not os.path.exists(cpp_program):
        return []  # Если файл не существует - возвращаем пустой список
    try:
        loop = asyncio.get_event_loop()  # Получаем цикл событий
        # Запускаем C++ программу в отдельном потоке (чтобы не блокировать асинхронность)
        result = await loop.run_in_executor(
            None,  # Используем стандартный ThreadPoolExecutor
            lambda: subprocess.run(
                [cpp_program, genres_str, RAWG_API_KEY, str(page)],  # Аргументы командной строки
                capture_output=True,  # Захватываем stdout и stderr
                text=True,  # Возвращаем строки, а не байты
                timeout=30,  # Таймаут 30 секунд
                encoding='utf-8'  # Кодировка UTF-8
            )
        )
        if result.returncode != 0:  # Если программа завершилась с ошибкой
            return []
        output = result.stdout.strip()  # Получаем вывод программы
        if not output:
            return []
        games = []
        # Парсим вывод построчно (формат: ID|Name|Genre)
        for line in output.split('\n'):
            line = line.strip()
            if not line or '|' not in line:  # Пропускаем пустые строки без разделителя
                continue
            parts = line.split('|')
            if len(parts) >= 3:  # Должно быть минимум 3 части
                try:
                    game_id = int(parts[0])  # Первая часть - ID
                    name = parts[1]  # Вторая часть - название
                    genre = parts[2]  # Третья часть - жанр
                    games.append(GameRecommendation(id=game_id, name=name, genre=genre))
                except:
                    continue  # Игнорируем ошибочные строки
        # Фильтруем игры без жанра
        games = [g for g in games if g.genre and g.genre.strip()]
        return games
    except Exception as e:  # Ловим любые исключения
        print(f"[DEBUG] Exception: {e}")
        return []

# Эндпоинт для получения персональных рекомендаций
@app.get("/recommendations", response_model=List[GameRecommendation])
async def recommendations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Получаем все игры пользователя
    user_games = db.query(Game).filter(Game.owner_id == current_user.id).all()
    # Если коллекция пуста - возвращаем популярные игры
    if not user_games:
        popular = await get_recommendations_from_cpp("popular")
        return popular[:5]  # Только первые 5

    # Собираем жанры пользователя и преобразуем в английские слэги для RAWG API
    user_genres = set()
    # Словарь для маппинга русских/альтернативных названий жанров в английские слэги
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
            # Приводим к нижнему регистру и маппим, если есть
            slug = genre_map.get(g.genre.lower(), g.genre.lower())
            user_genres.add(slug)

    # Если после маппинга жанров нет - возвращаем популярные
    if not user_genres:
        popular = await get_recommendations_from_cpp("popular")
        return popular[:5]

    # Формируем строку жанров через запятую для API
    genres_str = ",".join(user_genres)
    raw_recs = await get_recommendations_from_cpp(genres_str)

    # Фильтр 1: исключаем игры без жанра
    raw_recs = [g for g in raw_recs if g.genre.strip()]

    # Фильтр 2: оставляем только те, чей жанр входит в user_genres
    allowed_genres = {genre.lower() for genre in user_genres}
    filtered_by_genre = [g for g in raw_recs if g.genre.lower() in allowed_genres]

    # Фильтр 3: исключаем уже добавленные в коллекцию игры
    existing_ids = {g.external_id for g in user_games if g.external_id}
    filtered = [g for g in filtered_by_genre if g.id not in existing_ids]

    # Если после всех фильтров ничего не осталось - возвращаем популярные
    if not filtered:
        popular = await get_recommendations_from_cpp("popular")
        return popular[:5]

    # Возвращаем первые 5 рекомендаций
    return filtered[:5]

# Serve static files
# Монтируем статические файлы из папки "static" для обслуживания на корневом пути
app.mount("/", StaticFiles(directory="static", html=True), name="static")