import logging
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import EmailStr

from app.core.database import get_db
from app.models.models import Clinic, User, VerificationStatus
from app.schemas.schemas import UserCreate, UserResponse, Token
from app.core.security import (
    create_access_token,
    get_password_hash,
    store_license_certificate,
    validate_dental_license_format,
    verify_password,
)
from app.services.security_audit import record_security_event

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    email: EmailStr = Form(...),
    full_name: str = Form(..., min_length=1, max_length=200),
    password: str = Form(..., min_length=8, max_length=128),
    clinic_name: str = Form(..., min_length=1, max_length=200),
    dental_license_number: str = Form(..., min_length=4, max_length=32),
    issuing_council: str = Form(..., min_length=2, max_length=120),
    license_certificate: UploadFile = File(...),
    clinic_mobile: str | None = Form(default=None),
    clinic_operating_hours: str | None = Form(default=None, max_length=2000),
    clinic_scheduling_context: str | None = Form(default=None, max_length=4000),
    db: Session = Depends(get_db),
):
    certificate_path: str | None = None
    try:
        user_data = UserCreate(
            email=email,
            full_name=full_name,
            password=password,
            clinic_name=clinic_name,
            dental_license_number=dental_license_number,
            issuing_council=issuing_council,
            clinic_mobile=clinic_mobile,
            clinic_operating_hours=clinic_operating_hours,
            clinic_scheduling_context=clinic_scheduling_context,
        )
        normalized_license = user_data.dental_license_number.strip().upper()
        if not validate_dental_license_format(normalized_license, user_data.issuing_council):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Dental license number or issuing council format is invalid",
            )

        existing_user = db.query(User).filter(User.email == user_data.email).first()
        existing_license = db.query(Clinic).filter(
            Clinic.license_number == normalized_license
        ).first()
        if existing_user or existing_license:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or dental license number is already registered",
            )

        certificate_content = await license_certificate.read(5 * 1024 * 1024 + 1)
        await license_certificate.close()
        if not certificate_content or len(certificate_content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="License certificate must be no larger than 5 MB",
            )
        try:
            certificate_path = store_license_certificate(certificate_content)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        clinic = Clinic(
            name=user_data.clinic_name,
            registered_mobile=user_data.clinic_mobile,
            license_number=normalized_license,
            issuing_council=user_data.issuing_council.strip(),
            verification_status=VerificationStatus.PENDING,
            operating_hours=user_data.clinic_operating_hours,
            scheduling_context=user_data.clinic_scheduling_context,
        )
        db.add(clinic)
        db.flush()

        db_user = User(
            clinic_id=clinic.id,
            email=str(user_data.email),
            full_name=user_data.full_name,
            hashed_password=get_password_hash(user_data.password),
            role="CLINIC_ADMIN",
            license_number=normalized_license,
            issuing_council=user_data.issuing_council.strip(),
            verification_status=VerificationStatus.PENDING,
            license_certificate_path=certificate_path,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except HTTPException:
        db.rollback()
        if certificate_path:
            try:
                os.remove(certificate_path)
            except OSError:
                logger.exception("Failed to remove uncommitted license certificate")
        raise
    except IntegrityError:
        db.rollback()
        if certificate_path:
            try:
                os.remove(certificate_path)
            except OSError:
                logger.exception("Failed to remove uncommitted license certificate")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email, clinic mobile, or dental license number is already registered",
        )
    except SQLAlchemyError:
        db.rollback()
        if certificate_path:
            try:
                os.remove(certificate_path)
            except OSError:
                logger.exception("Failed to remove uncommitted license certificate")
        logger.exception("Database error while registering clinic account")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register clinic account",
        )
    except Exception:
        db.rollback()
        if certificate_path:
            try:
                os.remove(certificate_path)
            except OSError:
                logger.exception("Failed to remove uncommitted license certificate")
        logger.exception("Unexpected error while registering clinic account")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register clinic account",
        )

@router.post("/login", response_model=Token)
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        record_security_event(db, request, "LOGIN_FAILED_INVALID_CREDENTIALS", user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clinic = db.query(Clinic).filter(Clinic.id == user.clinic_id).first()
    if (
        user.verification_status != VerificationStatus.VERIFIED
        or clinic is None
        or clinic.verification_status != VerificationStatus.VERIFIED
    ):
        record_security_event(db, request, "LOGIN_BLOCKED_UNVERIFIED_LICENSE", user)
        if (
            user.verification_status == VerificationStatus.REVOKED
            or (clinic is not None and clinic.verification_status == VerificationStatus.REVOKED)
        ):
            detail = "Dental license verification has been revoked. Access is restricted."
        elif (
            user.verification_status == VerificationStatus.REJECTED
            or (clinic is not None and clinic.verification_status == VerificationStatus.REJECTED)
        ):
            detail = "Dental license verification was rejected. Access is restricted."
        else:
            detail = "Account Pending Dental Council Verification. Unauthorized access is restricted."
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
    if user.role not in {"DENTIST", "CLINIC_ADMIN"} or clinic.subscription_status != "active":
        record_security_event(db, request, "LOGIN_BLOCKED_UNAUTHORIZED_ROLE", user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinical access is restricted to verified dentists and clinic administrators.",
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "clinic_id": user.clinic_id}
    )
    return {"access_token": access_token, "token_type": "bearer"}