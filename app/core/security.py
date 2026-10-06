from datetime import datetime, timedelta
import os
import re
from pathlib import Path
from uuid import uuid4
from typing import Optional
from jose import jwt
from passlib.context import CryptContext

_DEVELOPMENT_SECRET = "development-only-change-this-jwt-secret-before-deployment"
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("APP_ENV", "development").lower() in {"production", "prod"}:
        raise RuntimeError("JWT_SECRET_KEY must be set in production")
    SECRET_KEY = _DEVELOPMENT_SECRET
if len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
LICENSE_NUMBER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9/-]{3,31}$")

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    deprecated="auto",
)


def validate_dental_license_format(license_number: str, issuing_council: str) -> bool:
    normalized_number = license_number.strip().upper()
    normalized_council = issuing_council.strip()
    return bool(
        LICENSE_NUMBER_PATTERN.fullmatch(normalized_number)
        and 2 <= len(normalized_council) <= 120
    )


def license_certificate_directory() -> Path:
    default_directory = Path(__file__).resolve().parents[2] / "private_uploads" / "licenses"
    return Path(os.getenv("LICENSE_CERTIFICATE_DIR", str(default_directory))).resolve()


def store_license_certificate(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        extension = ".pdf"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = ".png"
    elif content.startswith(b"\xff\xd8\xff"):
        extension = ".jpg"
    else:
        raise ValueError("Certificate must be a valid PDF, PNG, or JPEG file")

    directory = license_certificate_directory()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        directory.chmod(0o700)
    except OSError:
        pass

    destination = directory / f"{uuid4().hex}{extension}"
    with destination.open("xb") as certificate_file:
        certificate_file.write(content)
    return str(destination)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt