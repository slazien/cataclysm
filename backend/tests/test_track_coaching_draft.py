"""Tests for AI coaching notes draft generation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.services.track_coaching_draft import (
    CornerCoachingDraft,
    generate_coaching_drafts,
)

_PATCH_ANTHROPIC = "backend.api.services.track_coaching_draft.anthropic"


def _make_mock_response(notes_json: str) -> MagicMock:
    """Build a mock Anthropic response with the given text content."""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=notes_json)]
    return mock_resp


def _mock_client(response: MagicMock) -> AsyncMock:
    """Build a mock AsyncAnthropic client returning *response*."""
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


class TestGenerateCoachingDrafts:
    @pytest.mark.asyncio
    async def test_generates_notes_for_each_corner(self) -> None:
        corners = [
            {"number": 1, "name": "T1", "direction": "left", "corner_type": "hairpin"},
            {"number": 2, "name": "T2", "direction": "right", "corner_type": "sweeper"},
        ]

        resp = _make_mock_response(
            json.dumps(
                [
                    {"number": 1, "note": "Brake late, turn in tight."},
                    {"number": 2, "note": "Smooth arc, use all the road."},
                ]
            )
        )
        client = _mock_client(resp)

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch(_PATCH_ANTHROPIC) as mock_mod,
        ):
            mock_mod.AsyncAnthropic.return_value = client
            drafts = await generate_coaching_drafts(corners, track_name="Test Track")

        assert len(drafts) == 2
        assert drafts[0].corner_number == 1
        assert drafts[0].corner_name == "T1"
        assert "Brake" in drafts[0].coaching_note
        assert isinstance(drafts[0], CornerCoachingDraft)
        assert drafts[1].corner_number == 2
        assert drafts[1].coaching_note == "Smooth arc, use all the road."

    @pytest.mark.asyncio
    async def test_no_api_key_returns_empty(self) -> None:
        import os

        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            drafts = await generate_coaching_drafts(
                [{"number": 1, "name": "T1"}], track_name="Test"
            )
            assert drafts == []
        finally:
            if old is not None:
                os.environ["ANTHROPIC_API_KEY"] = old

    @pytest.mark.asyncio
    async def test_router_mode_does_not_require_anthropic_key(self) -> None:
        corners = [{"number": 1, "name": "T1"}]
        routed = MagicMock(text=json.dumps([{"number": 1, "note": "Brake in a straight line."}]))

        with (
            patch.dict(
                "os.environ",
                {"LLM_ROUTING_ENABLED": "1", "OPENAI_API_KEY": "sk-openai"},
                clear=True,
            ),
            patch("backend.api.services.track_coaching_draft.is_task_available", return_value=True),
            patch(
                "backend.api.services.track_coaching_draft.call_text_completion",
                return_value=routed,
            ),
            patch(_PATCH_ANTHROPIC) as mock_mod,
        ):
            drafts = await generate_coaching_drafts(corners, track_name="Test")

        assert len(drafts) == 1
        assert drafts[0].corner_number == 1
        assert "Brake" in drafts[0].coaching_note
        mock_mod.AsyncAnthropic.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self) -> None:
        client = AsyncMock()
        client.messages.create = AsyncMock(side_effect=Exception("API error"))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch(_PATCH_ANTHROPIC) as mock_mod,
        ):
            mock_mod.AsyncAnthropic.return_value = client
            drafts = await generate_coaching_drafts(
                [{"number": 1, "name": "T1"}], track_name="Test"
            )
        assert drafts == []

    @pytest.mark.asyncio
    async def test_handles_markdown_json_code_block(self) -> None:
        corners = [{"number": 1, "name": "T1", "direction": "left"}]
        resp = _make_mock_response('```json\n[{"number": 1, "note": "Trail brake in."}]\n```')
        client = _mock_client(resp)

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch(_PATCH_ANTHROPIC) as mock_mod,
        ):
            mock_mod.AsyncAnthropic.return_value = client
            drafts = await generate_coaching_drafts(corners, track_name="Test Track")

        assert len(drafts) == 1
        assert drafts[0].coaching_note == "Trail brake in."

    @pytest.mark.asyncio
    async def test_handles_plain_code_block(self) -> None:
        corners = [{"number": 3, "name": "Esses", "direction": "right"}]
        resp = _make_mock_response('```\n[{"number": 3, "note": "Commit early."}]\n```')
        client = _mock_client(resp)

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch(_PATCH_ANTHROPIC) as mock_mod,
        ):
            mock_mod.AsyncAnthropic.return_value = client
            drafts = await generate_coaching_drafts(corners, track_name="Test Track")

        assert len(drafts) == 1
        assert drafts[0].corner_number == 3
        assert drafts[0].corner_name == "Esses"

    @pytest.mark.asyncio
    async def test_empty_corners_returns_empty(self) -> None:
        # Should not even check for API key — early return
        drafts = await generate_coaching_drafts([], track_name="Test")
        assert drafts == []

    @pytest.mark.asyncio
    async def test_includes_track_length_in_prompt(self) -> None:
        corners = [{"number": 1, "name": "T1"}]
        resp = _make_mock_response(json.dumps([{"number": 1, "note": "Brake early."}]))
        client = _mock_client(resp)

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch(_PATCH_ANTHROPIC) as mock_mod,
        ):
            mock_mod.AsyncAnthropic.return_value = client
            await generate_coaching_drafts(corners, track_name="Barber", track_length_m=3700.0)

        call_kwargs = client.messages.create.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        assert "3700m" in user_msg
        assert "Barber" in user_msg

    @pytest.mark.asyncio
    async def test_builds_full_corner_description(self) -> None:
        corners = [
            {
                "number": 5,
                "name": "T5",
                "direction": "left",
                "corner_type": "chicane",
                "elevation_trend": "downhill",
                "camber": "positive",
            }
        ]
        resp = _make_mock_response(json.dumps([{"number": 5, "note": "Brake downhill."}]))
        client = _mock_client(resp)

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch(_PATCH_ANTHROPIC) as mock_mod,
        ):
            mock_mod.AsyncAnthropic.return_value = client
            await generate_coaching_drafts(corners, track_name="Test")

        call_kwargs = client.messages.create.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        assert "left-hander" in user_msg
        assert "chicane" in user_msg
        assert "downhill" in user_msg
        assert "positive camber" in user_msg

    @pytest.mark.asyncio
    async def test_missing_corner_name_uses_fallback(self) -> None:
        corners: list[dict[str, object]] = [{"number": 7}]
        resp = _make_mock_response(json.dumps([{"number": 7, "note": "Stay wide."}]))
        client = _mock_client(resp)

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch(_PATCH_ANTHROPIC) as mock_mod,
        ):
            mock_mod.AsyncAnthropic.return_value = client
            drafts = await generate_coaching_drafts(corners, track_name="Test")

        assert len(drafts) == 1
        assert drafts[0].corner_name == "T7"
