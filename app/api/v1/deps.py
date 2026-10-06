from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import SECRET_KEY, ALGORITHM
from app.models.models import Clinic, User, VerificationStatus
from app.schemas.schemas import TokenData
from app.services.security_audit import record_security_event

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        clinic_id = payload.get("clinic_id")
        if email is None or clinic_id is None:
            raise credentials_exception
        token_data = TokenData(email=email, role=role, clinic_id=clinic_id)
    except JWTError:
        raise credentials_exception
    
    user = (
        db.query(User)
        .join(Clinic)
        .filter(
            User.email == token_data.email,
            User.clinic_id == token_data.clinic_id,
            Clinic.id == token_data.clinic_id,
            Clinic.subscription_status == "active",
        )
        .first()
    )
    if user is None:
        raise credentials_exception
    return user

def require_role(allowed_roles: list[str]):
    def role_dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{current_user.role}'. Required roles: {allowed_roles}"
            )
        return current_user
    return role_dependency


def verify_active_dentist(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    clinic = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()
    allowed_roles = {"DENTIST", "CLINIC_ADMIN"}
    if (
        current_user.role not in allowed_roles
        or current_user.verification_status != VerificationStatus.VERIFIED
        or clinic is None
        or clinic.verification_status != VerificationStatus.VERIFIED
        or clinic.subscription_status != "active"
    ):
        record_security_event(db, request, "UNVERIFIED_OR_UNAUTHORIZED_ACCESS", current_user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account Pending Dental Council Verification. Unauthorized access is restricted.",
        )
    return current_user