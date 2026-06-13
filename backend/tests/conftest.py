"""
Shared test fixtures for Gesture-Ease backend tests.
Uses SQLite in-memory database so no MySQL is required.
"""

import pytest
import numpy as np
import sys
import os
from unittest.mock import MagicMock, patch

# Point to SQLite before any app code runs
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test-secret-key'

# Mock heavy/system dependencies before any imports
sys.modules['tensorflow'] = MagicMock()
sys.modules['tensorflow.keras'] = MagicMock()
sys.modules['tensorflow.keras.models'] = MagicMock()
sys.modules['cv2'] = MagicMock()
sys.modules['mediapipe'] = MagicMock()
sys.modules['jwt'] = MagicMock()
sys.modules['pymysql'] = MagicMock()

# Mock auth module
_auth_mock = MagicMock()
_auth_mock.generate_token.return_value = 'mock-token-1-testuser'
_auth_mock.verify_token.return_value = {'user_id': 1, 'username': 'testuser'}
_auth_mock.token_required = lambda f: f
sys.modules['auth'] = _auth_mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import app with init_app patched so the module-level MySQL init is skipped
with patch('flask_sqlalchemy.SQLAlchemy.init_app'):
    import app as flask_app

from database import db, User, UserProgress, GestureAttempt

# Configure for SQLite once — the Flask app is a singleton
flask_app.app.config.update({
    'TESTING': True,
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'SQLALCHEMY_ENGINE_OPTIONS': {},
})
db.init_app(flask_app.app)  # Register SQLAlchemy with the real SQLite config


@pytest.fixture(scope='function')
def app():
    """Provide the Flask app with a fresh database for each test."""
    with flask_app.app.app_context():
        db.create_all()
        yield flask_app.app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_user(app):
    with app.app_context():
        user = User(username='testuser', email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        return user.id


@pytest.fixture
def landmark_sequence():
    return np.random.rand(30, 126).astype(np.float32)
