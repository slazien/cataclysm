"""Tests for cataclysm.topic_guardrail."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from cataclysm.topic_guardrail import (
    OFF_TOPIC_RESPONSE,
    TOPIC_RESTRICTION_PROMPT,
    TopicClassification,
    _parse_classification,
    classify_topic,
)


# ---------------------------------------------------------------------------
# Tests: _parse_classification
# ---------------------------------------------------------------------------


class TestParseClassification:
    def test_parses_on_topic_true(self) -> None:
        result = _parse_classification('{"on_topic": true}')
        assert result.on_topic is True
        assert result.source == "classifier"

    def test_parses_on_topic_false(self) -> None:
        result = _parse_classification('{"on_topic": false}')
        assert result.on_topic is False
        assert result.source == "classifier"

    def test_parses_json_in_code_block(self) -> None:
        result = _parse_classification('```json\n{"on_topic": false}\n```')
        assert result.on_topic is False

    def test_parses_json_with_surrounding_text(self) -> None:
        result = _parse_classification('The answer is: {"on_topic": true} based on analysis.')
        assert result.on_topic is True

    def test_invalid_json_falls_open(self) -> None:
        result = _parse_classification("not json at all")
        assert result.on_topic is True
        assert result.source == "fallback"

    def test_empty_json_falls_open(self) -> None:
        result = _parse_classification("{}")
        assert result.on_topic is True  # default is True (fail open)

    def test_whitespace_handling(self) -> None:
        result = _parse_classification('  \n {"on_topic": false} \n ')
        assert result.on_topic is False


# ---------------------------------------------------------------------------
# Tests: classify_topic (mocked API)
# ---------------------------------------------------------------------------


def _make_mock_anthropic(response_text: str) -> MagicMock:
    """Create a mock anthropic module returning the given text."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mock_module = MagicMock()
    mock_module.Anthropic.return_value = mock_client
    return mock_module


class TestClassifyTopic:
    def test_on_topic_classified(self) -> None:
        mock = _make_mock_anthropic('{"on_topic": true}')
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock}),
        ):
            result = classify_topic("How should I trail brake into turn 5?")
        assert result.on_topic is True
        assert result.source == "classifier"

    def test_off_topic_classified(self) -> None:
        mock = _make_mock_anthropic('{"on_topic": false}')
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock}),
        ):
            result = classify_topic("How do I make an apple pie?")
        assert result.on_topic is False
        assert result.source == "classifier"

    def test_no_api_key_falls_open(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = classify_topic("How do I make an apple pie?")
        assert result.on_topic is True
        assert result.source == "no_api_key"

    def test_empty_message_is_off_topic(self) -> None:
        result = classify_topic("")
        assert result.on_topic is False
        assert result.source == "empty"

    def test_whitespace_only_is_off_topic(self) -> None:
        result = classify_topic("   \n  ")
        assert result.on_topic is False
        assert result.source == "empty"

    def test_api_error_falls_open(self) -> None:
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")
        mock_module.Anthropic.return_value = mock_client

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock_module}),
        ):
            result = classify_topic("How do I make an apple pie?")
        assert result.on_topic is True
        assert result.source == "fallback"

    def test_uses_haiku_model(self) -> None:
        mock = _make_mock_anthropic('{"on_topic": true}')
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock}),
        ):
            classify_topic("What's my braking point for T3?")

        call_kwargs = mock.Anthropic.return_value.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs.kwargs["max_tokens"] == 32

    def test_message_included_in_prompt(self) -> None:
        mock = _make_mock_anthropic('{"on_topic": true}')
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}),
            patch.dict(sys.modules, {"anthropic": mock}),
        ):
            classify_topic("Am I trail braking enough into turn 5?")

        call_kwargs = mock.Anthropic.return_value.messages.create.call_args
        prompt_text = call_kwargs.kwargs["messages"][0]["content"]
        assert "trail braking" in prompt_text


# ---------------------------------------------------------------------------
# Tests: TOPIC_RESTRICTION_PROMPT content
# ---------------------------------------------------------------------------


class TestTopicRestrictionPrompt:
    def test_includes_topic_restriction_header(self) -> None:
        assert "Topic Restriction" in TOPIC_RESTRICTION_PROMPT

    def test_includes_allowed_topics(self) -> None:
        prompt = TOPIC_RESTRICTION_PROMPT.lower()
        assert "driving technique" in prompt
        assert "telemetry" in prompt
        assert "vehicle dynamics" in prompt

    def test_includes_decline_instruction(self) -> None:
        assert "motorsport driving coach" in TOPIC_RESTRICTION_PROMPT

    def test_includes_redirect_message(self) -> None:
        assert "What would you like to know about your driving?" in TOPIC_RESTRICTION_PROMPT


# ---------------------------------------------------------------------------
# Tests: OFF_TOPIC_RESPONSE
# ---------------------------------------------------------------------------


class TestOffTopicResponse:
    def test_is_polite_redirect(self) -> None:
        assert "motorsport driving coach" in OFF_TOPIC_RESPONSE
        assert "driving" in OFF_TOPIC_RESPONSE.lower()

    def test_not_empty(self) -> None:
        assert len(OFF_TOPIC_RESPONSE) > 20


# ---------------------------------------------------------------------------
# Tests: Edge cases — driving-adjacent topics
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Verify the classifier prompt is broad enough for driving-adjacent topics."""

    def test_classifier_prompt_covers_car_setup(self) -> None:
        """Car setup/modifications should be on-topic per the prompt."""
        from cataclysm.topic_guardrail import _CLASSIFIER_PROMPT

        prompt_lower = _CLASSIFIER_PROMPT.lower()
        assert "setup" in prompt_lower
        assert "suspension" in prompt_lower

    def test_classifier_prompt_covers_general_motorsport(self) -> None:
        """F1, karting, etc. should be on-topic per the prompt."""
        from cataclysm.topic_guardrail import _CLASSIFIER_PROMPT

        prompt_lower = _CLASSIFIER_PROMPT.lower()
        assert "f1" in prompt_lower
        assert "karting" in prompt_lower

    def test_classifier_prompt_covers_fitness(self) -> None:
        """Driver fitness should be on-topic per the prompt."""
        from cataclysm.topic_guardrail import _CLASSIFIER_PROMPT

        prompt_lower = _CLASSIFIER_PROMPT.lower()
        assert "fitness" in prompt_lower

    def test_classifier_prompt_tangential_is_allowed(self) -> None:
        """The prompt says 'even tangentially' — broad coverage."""
        from cataclysm.topic_guardrail import _CLASSIFIER_PROMPT

        assert "tangentially" in _CLASSIFIER_PROMPT.lower()
