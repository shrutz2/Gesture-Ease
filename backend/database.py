"""
Database models and configuration for Gesture-Ease
Using SQLAlchemy ORM with MySQL backend
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class User(db.Model):
    """User model for storing user accounts"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    progress = db.relationship('UserProgress', backref='user', lazy=True, cascade='all, delete-orphan')
    attempts = db.relationship('GestureAttempt', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'user_id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'stats': self.get_stats()
        }
    
    def get_stats(self):
        """Calculate user statistics"""
        total_attempts = len(self.attempts)
        correct_attempts = len([a for a in self.attempts if a.is_correct])
        
        accuracy = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
        
        # Get progress data
        total_points = sum([a.points for a in self.attempts])
        
        # Get word statistics
        words_practiced = list(set([a.target_word for a in self.attempts]))
        
        return {
            'level': 1 + (total_points // 100),
            'total_points': total_points,
            'current_streak': self._calculate_current_streak(),
            'longest_streak': self._calculate_longest_streak(),
            'total_attempts': total_attempts,
            'correct_attempts': correct_attempts,
            'accuracy': round(accuracy, 2),
            'words_practiced': words_practiced,
            'words_mastered': len([w for w in words_practiced if self._word_accuracy(w) >= 70])
        }
    
    def _calculate_current_streak(self):
        """Calculate current streak (consecutive correct attempts)"""
        if not self.attempts:
            return 0
        
        streak = 0
        for attempt in sorted(self.attempts, key=lambda x: x.created_at, reverse=True):
            if attempt.is_correct:
                streak += 1
            else:
                break
        return streak
    
    def _calculate_longest_streak(self):
        """Calculate longest streak ever"""
        if not self.attempts:
            return 0
        
        sorted_attempts = sorted(self.attempts, key=lambda x: x.created_at)
        longest = 0
        current = 0
        
        for attempt in sorted_attempts:
            if attempt.is_correct:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        
        return longest
    
    def _word_accuracy(self, word):
        """Calculate accuracy for a specific word"""
        word_attempts = [a for a in self.attempts if a.target_word.lower() == word.lower()]
        if not word_attempts:
            return 0
        
        correct = len([a for a in word_attempts if a.is_correct])
        return (correct / len(word_attempts)) * 100


class UserProgress(db.Model):
    """Track user progress on specific words"""
    __tablename__ = 'user_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    word = db.Column(db.String(120), nullable=False, index=True)
    attempts = db.Column(db.Integer, default=0)
    correct = db.Column(db.Integer, default=0)
    confidence = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_accuracy(self):
        """Get accuracy percentage for this word"""
        if self.attempts == 0:
            return 0
        return (self.correct / self.attempts) * 100
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'word': self.word,
            'attempts': self.attempts,
            'correct': self.correct,
            'accuracy': self.get_accuracy(),
            'confidence': round(self.confidence, 3),
            'updated_at': self.updated_at.isoformat()
        }


class GestureAttempt(db.Model):
    """Log individual gesture attempts for analytics"""
    __tablename__ = 'gesture_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    target_word = db.Column(db.String(120), nullable=False, index=True)
    predicted_word = db.Column(db.String(120))
    target_confidence = db.Column(db.Float)
    is_correct = db.Column(db.Boolean, default=False, index=True)
    points = db.Column(db.Integer, default=0)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # For debugging
    top_predictions = db.Column(db.JSON)  # Store top 5 predictions as JSON
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'target_word': self.target_word,
            'predicted_word': self.predicted_word,
            'target_confidence': round(self.target_confidence, 3) if self.target_confidence else 0,
            'is_correct': self.is_correct,
            'points': self.points,
            'feedback': self.feedback,
            'created_at': self.created_at.isoformat(),
            'top_predictions': self.top_predictions
        }


class LeaderboardEntry(db.Model):
    """Pre-calculated leaderboard entries for performance"""
    __tablename__ = 'leaderboard'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rank = db.Column(db.Integer, index=True)
    total_points = db.Column(db.Integer, default=0, index=True)
    total_attempts = db.Column(db.Integer, default=0)
    accuracy = db.Column(db.Float, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        user = User.query.get(self.user_id)
        return {
            'rank': self.rank,
            'username': user.username if user else 'Unknown',
            'total_points': self.total_points,
            'total_attempts': self.total_attempts,
            'accuracy': round(self.accuracy, 2)
        }


def init_db(app):
    """Initialize database"""
    with app.app_context():
        db.create_all()
        print("[CHECK] Database initialized successfully!")


def reset_db(app):
    """Reset database (use with caution!)"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("⚠️ Database reset successfully!")
