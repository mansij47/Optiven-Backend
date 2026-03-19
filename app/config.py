import os
from dotenv import load_dotenv

load_dotenv()


def _get_int_env(key: str, default: int) -> int:
	value = os.getenv(key)
	if value is None or str(value).strip() == "":
		return default
	try:
		return int(str(value).strip())
	except ValueError:
		return default

DATABASE_NAME = os.getenv("DATABASE_NAME")
MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
LOGIN_URL = os.getenv("LOGIN_URL", "http://localhost:5173/login")

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = _get_int_env("EMAIL_PORT", 587)
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TIMEOUT_SECONDS = _get_int_env("EMAIL_TIMEOUT_SECONDS", 20)

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")