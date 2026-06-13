"""Tests for landmark sequence normalization logic."""

import pytest
import numpy as np

# conftest.py sets up all mocks before import — just import the function directly
from app import normalize_landmark_sequence


class TestNormalizeLandmarkSequence:
    def test_exact_length_unchanged(self):
        seq = np.random.rand(30, 126).astype(np.float32)
        result = normalize_landmark_sequence(seq, target_length=30)
        assert result.shape == (30, 126)
        np.testing.assert_array_equal(result, seq)

    def test_too_long_downsampled(self):
        seq = np.random.rand(60, 126).astype(np.float32)
        result = normalize_landmark_sequence(seq, target_length=30)
        assert result.shape == (30, 126)

    def test_too_short_padded(self):
        seq = np.random.rand(10, 126).astype(np.float32)
        result = normalize_landmark_sequence(seq, target_length=30)
        assert result.shape == (30, 126)
        np.testing.assert_array_equal(result[-1], seq[-1])

    def test_single_frame_padded(self):
        seq = np.random.rand(1, 126).astype(np.float32)
        result = normalize_landmark_sequence(seq, target_length=30)
        assert result.shape == (30, 126)
        for i in range(30):
            np.testing.assert_array_equal(result[i], seq[0])

    def test_empty_sequence_raises(self):
        seq = np.array([]).reshape(0, 126).astype(np.float32)
        with pytest.raises(ValueError):
            normalize_landmark_sequence(seq, target_length=30)

    def test_output_is_numpy_array(self):
        seq = np.random.rand(20, 126).astype(np.float32)
        result = normalize_landmark_sequence(seq, target_length=30)
        assert isinstance(result, np.ndarray)

    def test_custom_target_length(self):
        seq = np.random.rand(50, 126).astype(np.float32)
        result = normalize_landmark_sequence(seq, target_length=15)
        assert result.shape == (15, 126)
