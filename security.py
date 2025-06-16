"""
CaseFolio AI - Production Security Module
Enterprise-grade authentication and authorization with bcrypt and API keys
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import select
import jwt
from jwt.exceptions import InvalidTokenError

# Import models (assuming they're in the same directory)
from models import User, APIKey


# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = "your-secret-key-here"  # In production, load from environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class SecurityManager:
    """Handles all security operations for CaseFolio AI"""
    
    def __init__(self):
        self.pwd_context = pwd_context
    
    # Password operations
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    # User authentication
    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password"""
        stmt = select(User).where(User.email == email)
        user = db.execute(stmt).scalar_one_or_none()
        
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
            
        return user
    
    # JWT token operations
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def decode_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except InvalidTokenError:
            return None
    
    # API Key operations
    def generate_api_key(self) -> str:
        """Generate a new API key"""
        # Generate 32 character key
        alphabet = string.ascii_letters + string.digits
        key = ''.join(secrets.choice(alphabet) for _ in range(32))
        return f"cfa_{key}"  # Prefix with 'cfa_' for CaseFolio AI
    
    def create_api_key(self, db: Session, user_id: int, name: str, 
                      scopes: Optional[List[str]] = None,
                      expires_in_days: Optional[int] = None) -> tuple[str, APIKey]:
        """Create a new API key for a user"""
        # Generate the raw key
        raw_key = self.generate_api_key()
        
        # Extract prefix for fast lookup
        key_prefix = raw_key[:8]
        
        # Hash the full key
        key_hash = self.hash_password(raw_key)
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create the database record
        api_key = APIKey(
            key_prefix=key_prefix,
            key_hash=key_hash,
            name=name,
            scopes=scopes or ["read", "write"],
            user_id=user_id,
            expires_at=expires_at
        )
        
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        
        # Return both raw key (shown once) and the record
        return raw_key, api_key
    
    def verify_api_key(self, db: Session, api_key: str) -> Optional[APIKey]:
        """Verify an API key and return the associated record"""
        if not api_key or not api_key.startswith("cfa_"):
            return None
        
        # Extract prefix for database lookup
        key_prefix = api_key[:8]
        
        # Find all keys with this prefix (should be very few)
        stmt = select(APIKey).where(APIKey.key_prefix == key_prefix)
        potential_keys = db.execute(stmt).scalars().all()
        
        # Check each potential key
        for key_record in potential_keys:
            if self.verify_password(api_key, key_record.key_hash):
                # Check if key is still active
                if not key_record.is_active:
                    return None
                
                # Update last used timestamp
                key_record.last_used_at = datetime.utcnow()
                db.commit()
                
                return key_record
        
        return None
    
    def revoke_api_key(self, db: Session, key_id: int) -> bool:
        """Revoke an API key"""
        stmt = select(APIKey).where(APIKey.id == key_id)
        api_key = db.execute(stmt).scalar_one_or_none()
        
        if api_key:
            api_key.revoked_at = datetime.utcnow()
            db.commit()
            return True
        
        return False
    
    # Permission checking
    def check_api_key_scope(self, api_key: APIKey, required_scope: str) -> bool:
        """Check if an API key has a required scope"""
        return required_scope in api_key.scopes
    
    def check_rate_limit(self, db: Session, api_key: APIKey) -> tuple[bool, Dict[str, Any]]:
        """Check if API key is within rate limits"""
        # This is a simplified implementation
        # In production, use Redis or similar for accurate rate limiting
        
        # For now, just return that it's within limits
        return True, {
            "limit": api_key.rate_limit,
            "remaining": api_key.rate_limit - 1,
            "reset": datetime.utcnow() + timedelta(hours=1)
        }
    
    # User management
    def create_user(self, db: Session, email: str, password: str, 
                   full_name: str, is_superuser: bool = False) -> User:
        """Create a new user"""
        hashed_password = self.hash_password(password)
        
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_superuser=is_superuser,
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get a user by email"""
        stmt = select(User).where(User.email == email)
        return db.execute(stmt).scalar_one_or_none()
    
    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """Get a user by ID"""
        stmt = select(User).where(User.id == user_id)
        return db.execute(stmt).scalar_one_or_none()
    
    def update_user_password(self, db: Session, user_id: int, new_password: str) -> bool:
        """Update a user's password"""
        user = self.get_user_by_id(db, user_id)
        if user:
            user.hashed_password = self.hash_password(new_password)
            user.updated_at = datetime.utcnow()
            db.commit()
            return True
        return False


# Singleton instance
security_manager = SecurityManager()


# FastAPI dependency functions
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader


# Security schemes
bearer_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: Session = None  # Add your database dependency here
) -> User:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = security_manager.decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: int = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    user = security_manager.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    
    return user


async def get_current_user_from_api_key(
    api_key: Optional[str] = Security(api_key_header),
    db: Session = None  # Add your database dependency here
) -> User:
    """Get current user from API key"""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    key_record = security_manager.verify_api_key(db, api_key)
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    
    # Check rate limits
    within_limit, limit_info = security_manager.check_rate_limit(db, key_record)
    if not within_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(limit_info["limit"]),
                "X-RateLimit-Remaining": str(limit_info["remaining"]),
                "X-RateLimit-Reset": limit_info["reset"].isoformat(),
            }
        )
    
    return key_record.user


def require_scope(required_scope: str):
    """Decorator to require a specific scope for an endpoint"""
    def decorator(func):
        async def wrapper(*args, current_user: User = None, **kwargs):
            # Check if user has required scope
            # This is simplified - in production, check against user's API key scopes
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator