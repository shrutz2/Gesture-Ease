"""Tests for database models: User stats, streak calculation, word accuracy."""

import pytest
from database import db, User, UserProgress, GestureAttempt


def make_attempt(user_id, word, is_correct, points=10):
    attempt = GestureAttempt(
        user_id=user_id,
        target_word=word,
        is_correct=is_correct,
        points=points if is_correct else 0,
        target_confidence=0.7 if is_correct else 0.1
    )
    db.session.add(attempt)


class TestUserModel:
    def test_password_hashing(self, app):
        with app.app_context():
            user = User(username='hashtest', email='hash@example.com')
            user.set_password('mypassword')
            assert user.password_hash != 'mypassword'
            assert user.check_password('mypassword') is True
            assert user.check_password('wrongpassword') is False

    def test_to_dict_has_required_fields(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user)
            d = user.to_dict()
            assert 'user_id' in d
            assert 'username' in d
            assert 'email' in d
            assert 'stats' in d

    def test_get_stats_empty_user(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user)
            stats = user.get_stats()
            assert stats['total_attempts'] == 0
            assert stats['total_points'] == 0
            assert stats['accuracy'] == 0
            assert stats['level'] == 1

    def test_get_stats_with_attempts(self, app, sample_user):
        with app.app_context():
            make_attempt(sample_user, 'hello', is_correct=True, points=15)
            make_attempt(sample_user, 'hello', is_correct=True, points=10)
            make_attempt(sample_user, 'bye', is_correct=False, points=0)
            db.session.commit()

            user = User.query.get(sample_user)
            stats = user.get_stats()
            assert stats['total_attempts'] == 3
            assert stats['correct_attempts'] == 2
            assert stats['total_points'] == 25
            assert round(stats['accuracy'], 2) == 66.67

    def test_level_increases_with_points(self, app, sample_user):
        with app.app_context():
            for _ in range(10):
                make_attempt(sample_user, 'hello', is_correct=True, points=15)
            db.session.commit()

            user = User.query.get(sample_user)
            stats = user.get_stats()
            assert stats['level'] > 1

    def test_current_streak_correct_attempts(self, app, sample_user):
        with app.app_context():
            make_attempt(sample_user, 'hello', is_correct=True)
            make_attempt(sample_user, 'yes', is_correct=True)
            make_attempt(sample_user, 'no', is_correct=True)
            db.session.commit()

            user = User.query.get(sample_user)
            assert user._calculate_current_streak() == 3

    def test_streak_breaks_on_incorrect(self, app, sample_user):
        from datetime import datetime, timedelta
        with app.app_context():
            base = datetime.utcnow()
            for i, (word, correct) in enumerate([('hello', True), ('yes', True), ('no', False)]):
                attempt = GestureAttempt(
                    user_id=sample_user, target_word=word,
                    is_correct=correct, points=10 if correct else 0,
                    target_confidence=0.7 if correct else 0.1,
                    created_at=base + timedelta(seconds=i)
                )
                db.session.add(attempt)
            db.session.commit()

            user = User.query.get(sample_user)
            assert user._calculate_current_streak() == 0

    def test_longest_streak_calculation(self, app, sample_user):
        with app.app_context():
            make_attempt(sample_user, 'a', is_correct=True)
            make_attempt(sample_user, 'b', is_correct=True)
            make_attempt(sample_user, 'c', is_correct=True)
            make_attempt(sample_user, 'd', is_correct=False)
            make_attempt(sample_user, 'e', is_correct=True)
            db.session.commit()

            user = User.query.get(sample_user)
            assert user._calculate_longest_streak() == 3

    def test_word_accuracy_calculation(self, app, sample_user):
        with app.app_context():
            make_attempt(sample_user, 'hello', is_correct=True)
            make_attempt(sample_user, 'hello', is_correct=True)
            make_attempt(sample_user, 'hello', is_correct=False)
            db.session.commit()

            user = User.query.get(sample_user)
            accuracy = user._word_accuracy('hello')
            assert round(accuracy, 2) == 66.67

    def test_word_accuracy_unknown_word(self, app, sample_user):
        with app.app_context():
            user = User.query.get(sample_user)
            assert user._word_accuracy('unknownword') == 0


class TestUserProgress:
    def test_accuracy_calculation(self, app, sample_user):
        with app.app_context():
            progress = UserProgress(user_id=sample_user, word='hello', attempts=4, correct=3)
            db.session.add(progress)
            db.session.commit()
            assert progress.get_accuracy() == 75.0

    def test_accuracy_zero_attempts(self, app, sample_user):
        with app.app_context():
            progress = UserProgress(user_id=sample_user, word='test', attempts=0, correct=0)
            assert progress.get_accuracy() == 0

    def test_to_dict_fields(self, app, sample_user):
        with app.app_context():
            progress = UserProgress(user_id=sample_user, word='hello', attempts=5, correct=4, confidence=0.82)
            db.session.add(progress)
            db.session.commit()
            d = progress.to_dict()
            assert d['word'] == 'hello'
            assert d['attempts'] == 5
            assert d['correct'] == 4
            assert d['accuracy'] == 80.0
