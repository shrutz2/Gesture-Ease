"""
JWT Authentication module for Gesture-Ease
Provides token generation and verification
"""

import jwt
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)

# Never ship a hardcoded/guessable secret. Require it from the environment;
# if it's missing, generate a strong random one at startup (tokens won't
# survive a restart, which is a safe default that forces proper config in prod).
JWT_SECRET = os.getenv('JWT_SECRET')
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET not set in environment - generated a random secret for this run. "
        "Set JWT_SECRET in production so tokens stay valid across restarts."
    )
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', 24))


def generate_token(user_id, username):
    """Generate JWT token for user"""
    try:
        payload = {
            'user_id': user_id,
            'username': username,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return token
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        return None


def verify_token(token):
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'success': False, 'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'success': False, 'error': 'Token required'}), 401
        
        payload = verify_token(token)
        if not payload:
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 401
        
        # Add user info to request context
        request.user_id = payload['user_id']
        request.username = payload['username']
        
        return f(*args, **kwargs)
    
    return decorated
