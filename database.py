# Импортируем функции для создания движка, колонок и типов из SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
# Импортируем функции для декларативного создания моделей и отношений
from sqlalchemy.ext.declarative import declarative_base
# Импортируем sessionmaker для создания сессий и relationship для связей между таблицами
from sqlalchemy.orm import sessionmaker, relationship

# URL для подключения к SQLite базе данных (файл games.db в текущей папке)
SQLALCHEMY_DATABASE_URL = "sqlite:///./games.db"
# Создаем движок SQLAlchemy
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Необходимо для SQLite с многопоточностью
)
# Создаем фабрику сессий (не автоматический коммит, не автоматический сброс)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаем базовый класс для декларативных моделей
Base = declarative_base()

# Определяем модель пользователя (таблица users)
class User(Base):
    __tablename__ = "users"  # Имя таблицы в БД
    
    id = Column(Integer, primary_key=True, index=True)  # Уникальный ID, первичный ключ, индексированный
    username = Column(String, unique=True, index=True)  # Имя пользователя, уникальное, индексированное
    hashed_password = Column(String)  # Хешированный пароль
    totp_secret = Column(String, nullable=True)  # Секрет для TOTP (2FA), может быть NULL
    is_2fa_enabled = Column(Integer, default=0)  # Флаг включения 2FA (0 - выкл, 1 - вкл)
    games = relationship("Game", back_populates="owner")  # Связь один-ко-многим с играми

# Определяем модель игры (таблица games)
class Game(Base):
    __tablename__ = "games"  # Имя таблицы в БД
    
    id = Column(Integer, primary_key=True, index=True)  # Уникальный ID игры в нашей БД
    title = Column(String, index=True)  # Название игры, индексированное для поиска
    genre = Column(String)  # Жанр игры
    external_id = Column(Integer, nullable=True)  # ID игры в RAWG API, может быть NULL
    owner_id = Column(Integer, ForeignKey("users.id"))  # Внешний ключ на пользователя-владельца
    owner = relationship("User", back_populates="games")  # Обратная связь с пользователем

# Создаем все таблицы в базе данных (если они еще не существуют)
Base.metadata.create_all(bind=engine)