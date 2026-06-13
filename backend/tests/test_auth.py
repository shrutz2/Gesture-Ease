"""Tests for user registration and login endpoints."""

import json
import pytest


class TestRegister:
    def test_register_success(self, client):
        res = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'securepass'
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data['success'] is True
        assert 'token' in data
        assert data['user']['username'] == 'newuser'

    def test_register_duplicate_email(self, client):
        payload = {'username': 'user1', 'email': 'dup@example.com', 'password': 'pass123'}
        client.post('/api/auth/register', json=payload)

        payload['username'] = 'user2'
        res = client.post('/api/auth/register', json=payload)
        assert res.status_code == 409
        assert res.get_json()['success'] is False

    def test_register_duplicate_username(self, client):
        client.post('/api/auth/register', json={
            'username': 'sameuser', 'email': 'a@example.com', 'password': 'pass123'
        })
        res = client.post('/api/auth/register', json={
            'username': 'sameuser', 'email': 'b@example.com', 'password': 'pass123'
        })
        assert res.status_code == 409

    def test_register_missing_email(self, client):
        res = client.post('/api/auth/register', json={
            'username': 'nomail', 'password': 'pass123'
        })
        assert res.status_code == 400

    def test_register_short_password(self, client):
        res = client.post('/api/auth/register', json={
            'username': 'shortpass', 'email': 'x@example.com', 'password': '123'
        })
        assert res.status_code == 400

    def test_register_invalid_email_format(self, client):
        res = client.post('/api/auth/register', json={
            'username': 'bademail', 'email': 'notanemail', 'password': 'pass123'
        })
        assert res.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        client.post('/api/auth/register', json={
            'username': 'loginuser', 'email': 'login@example.com', 'password': 'mypassword'
        })
        res = client.post('/api/auth/login', json={
            'email': 'login@example.com', 'password': 'mypassword'
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert 'token' in data

    def test_login_wrong_password(self, client):
        client.post('/api/auth/register', json={
            'username': 'loginuser2', 'email': 'login2@example.com', 'password': 'correct'
        })
        res = client.post('/api/auth/login', json={
            'email': 'login2@example.com', 'password': 'wrong'
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self, client):
        res = client.post('/api/auth/login', json={
            'email': 'ghost@example.com', 'password': 'anything'
        })
        assert res.status_code == 401

    def test_login_missing_fields(self, client):
        res = client.post('/api/auth/login', json={'email': 'only@example.com'})
        assert res.status_code == 400
