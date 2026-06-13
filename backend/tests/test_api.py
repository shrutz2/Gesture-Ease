"""Tests for core API endpoints: status, search, words, leaderboard."""

import pytest


class TestHealthAndStatus:
    def test_health_check(self, client):
        res = client.get('/health')
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'healthy'

    def test_status_endpoint(self, client):
        res = client.get('/api/status')
        assert res.status_code == 200
        data = res.get_json()
        assert 'model_loaded' in data
        assert 'sequence_length' in data
        assert 'feature_dimension' in data

    def test_model_info_when_not_loaded(self, client):
        res = client.get('/api/model_info')
        assert res.status_code == 503
        assert res.get_json()['model_loaded'] is False


class TestSearch:
    def test_search_get_returns_words(self, client):
        res = client.get('/api/search')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert isinstance(data['words'], list)

    def test_search_post_with_query(self, client):
        res = client.post('/api/search', json={'query': 'hello'})
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert 'words' in data

    def test_search_get_with_query_param(self, client):
        res = client.get('/api/search?q=yes')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True

    def test_search_options_preflight(self, client):
        res = client.options('/api/search')
        assert res.status_code in (200, 204)


class TestWords:
    def test_words_endpoint_returns_list(self, client):
        res = client.get('/api/words')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert isinstance(data['words'], list)


class TestLeaderboard:
    def test_leaderboard_returns_list(self, client):
        res = client.get('/api/leaderboard')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert isinstance(data['leaderboard'], list)


class TestPredictLandmarks:
    def test_predict_without_model_returns_503(self, client):
        res = client.post('/api/predict_landmarks', json={
            'target_word': 'hello',
            'landmarks': [[0.0] * 126] * 30
        })
        assert res.status_code == 503

    def test_predict_empty_landmarks_returns_400(self, client):
        res = client.post('/api/predict_landmarks', json={
            'target_word': 'hello',
            'landmarks': []
        })
        assert res.status_code in (400, 503)

    def test_predict_invalid_target_word(self, client):
        res = client.post('/api/predict_landmarks', json={
            'target_word': '',
            'landmarks': [[0.0] * 126] * 30
        })
        assert res.status_code in (400, 503)

    def test_predict_options_preflight(self, client):
        res = client.options('/api/predict_landmarks')
        assert res.status_code in (200, 204)


class TestSessionAndBuffer:
    def test_session_start(self, client):
        res = client.post('/api/session/start')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True

    def test_reset_buffer(self, client):
        res = client.post('/api/reset_buffer')
        assert res.status_code == 200
        assert res.get_json()['success'] is True


class TestAttemptSaving:
    def test_save_attempt_without_user_returns_400(self, client):
        res = client.post('/api/attempt', json={
            'target_word': 'hello',
            'is_correct': True,
            'points': 10
        })
        assert res.status_code == 400

    def test_save_attempt_nonexistent_user_returns_404(self, client):
        res = client.post('/api/attempt', json={
            'user_id': 99999,
            'target_word': 'hello',
            'is_correct': True,
            'points': 10
        })
        assert res.status_code == 404

    def test_save_attempt_valid_user(self, client, sample_user, app):
        res = client.post('/api/attempt', json={
            'user_id': sample_user,
            'target_word': 'hello',
            'is_correct': True,
            'target_confidence': 0.75,
            'points': 15,
            'message': 'Great job!'
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data['success'] is True
        assert data['points'] == 15
