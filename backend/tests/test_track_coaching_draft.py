"""Tests for AI coaching notes draft generation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.api.services.track_coaching_draft import (
    CornerCoachingDraft,
    generate_coaching_drafts,
)

_PATCH_IS_TASK_AVAILABLE = "backend.api.services.track_coaching_draft.is_task_available"
_PATCH_CALL_TEXT_COMPLETION = "backend.api.services.track_coaching_draft.call_text_completion"


def _make_completion_response(text: str) -> MagicMock:
    """Build a mock LLM gateway response object with text payload."""
    response = MagicMock()
    response.text = text
    return response


class TestGenerateCoachingDrafts:
    @pytest.mark.asyncio
    async def test_generates_notes_for_each_corner(self) -> None:
        corners = [
            {"number": 1, "name": "T1", "direction": "left", "corner_type": "hairpin"},
            {"number": 2, "name": "T2", "direction": "right", "corner_type": "sweeper"},
        ]

        response = _make_completion_response(
            json.dumps(
                [
                    {"number": 1, "note": "Brake late, turn in tight."},
                    {"number": 2, "note": "Smooth arc, use all the road."},
                ]
            )
        )

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response),
        ):
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
        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=False),
            patch(_PATCH_CALL_TEXT_COMPLETION) as mock_call,
        ):
            drafts = await generate_coaching_drafts(
                [{"number": 1, "name": "T1"}], track_name="Test"
            )

        assert len(drafts) == 1
        assert drafts[0].corner_number == 1
        assert drafts[0].corner_name == "T1"
        assert drafts[0].coaching_note
        mock_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_router_mode_does_not_require_anthropic_key(self) -> None:
        corners = [{"number": 1, "name": "T1"}]
        response = _make_completion_response(
            json.dumps([{"number": 1, "note": "Brake in a straight line."}])
        )

        with (
            patch.dict(
                "os.environ",
                {"LLM_ROUTING_ENABLED": "1", "OPENAI_API_KEY": "sk-openai"},
                clear=True,
            ),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response) as mock_call,
        ):
            drafts = await generate_coaching_drafts(corners, track_name="Test")

        assert len(drafts) == 1
        assert drafts[0].corner_number == 1
        assert "Brake" in drafts[0].coaching_note
        assert mock_call.call_count == 1
        assert mock_call.call_args.kwargs["default_provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self) -> None:
        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, side_effect=Exception("API error")),
        ):
            drafts = await generate_coaching_drafts(
                [{"number": 1, "name": "T1"}], track_name="Test"
            )
        assert len(drafts) == 1
        assert drafts[0].corner_number == 1
        assert drafts[0].corner_name == "T1"
        assert drafts[0].coaching_note

    @pytest.mark.asyncio
    async def test_handles_markdown_json_code_block(self) -> None:
        corners = [{"number": 1, "name": "T1", "direction": "left"}]
        response = _make_completion_response(
            '```json\n[{"number": 1, "note": "Trail brake in."}]\n```'
        )

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response),
        ):
            drafts = await generate_coaching_drafts(corners, track_name="Test Track")

        assert len(drafts) == 1
        assert drafts[0].coaching_note == "Trail brake in."

    @pytest.mark.asyncio
    async def test_handles_plain_code_block(self) -> None:
        corners = [{"number": 3, "name": "Esses", "direction": "right"}]
        response = _make_completion_response('```\n[{"number": 3, "note": "Commit early."}]\n```')

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response),
        ):
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
        response = _make_completion_response(json.dumps([{"number": 1, "note": "Brake early."}]))

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response) as mock_call,
        ):
            await generate_coaching_drafts(corners, track_name="Barber", track_length_m=3700.0)

        user_msg = mock_call.call_args.kwargs["user_content"]
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
        response = _make_completion_response(json.dumps([{"number": 5, "note": "Brake downhill."}]))

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response) as mock_call,
        ):
            await generate_coaching_drafts(corners, track_name="Test")

        user_msg = mock_call.call_args.kwargs["user_content"]
        assert "left-hander" in user_msg
        assert "chicane" in user_msg
        assert "downhill" in user_msg
        assert "positive camber" in user_msg

    @pytest.mark.asyncio
    async def test_missing_corner_name_uses_fallback(self) -> None:
        corners: list[dict[str, object]] = [{"number": 7}]
        response = _make_completion_response(json.dumps([{"number": 7, "note": "Stay wide."}]))

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response),
        ):
            drafts = await generate_coaching_drafts(corners, track_name="Test")

        assert len(drafts) == 1
        assert drafts[0].corner_name == "T7"

    @pytest.mark.asyncio
    async def test_stringified_corner_number_maps_to_existing_corner_name(self) -> None:
        corners = [{"number": 1, "name": "Turn One"}]
        response = _make_completion_response(
            json.dumps([{"number": "1.0", "note": "Hold a tight line at apex."}])
        )

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response),
        ):
            drafts = await generate_coaching_drafts(corners, track_name="Test")

        assert len(drafts) == 1
        assert drafts[0].corner_number == 1
        assert drafts[0].corner_name == "Turn One"

    @pytest.mark.asyncio
    async def test_invalid_corner_number_item_is_skipped_without_dropping_valid_entries(
        self,
    ) -> None:
        corners = [{"number": 1, "name": "T1"}, {"number": 2, "name": "T2"}]
        response = _make_completion_response(
            json.dumps(
                [
                    {"number": "bad-value", "note": "Ignore this malformed item."},
                    {"number": 2, "note": "Brake in a straight line, then release smoothly."},
                ]
            )
        )

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response),
        ):
            drafts = await generate_coaching_drafts(corners, track_name="Test")

        assert len(drafts) == 2
        assert drafts[0].corner_number == 1
        assert drafts[0].corner_name == "T1"
        assert drafts[0].coaching_note
        assert drafts[1].corner_number == 2
        assert drafts[1].corner_name == "T2"
        assert "Brake in a straight line" in drafts[1].coaching_note

    @pytest.mark.asyncio
    async def test_missing_llm_entry_is_backfilled_to_preserve_one_note_per_corner(self) -> None:
        corners = [{"number": 1, "name": "T1"}, {"number": 2, "name": "T2"}]
        response = _make_completion_response(json.dumps([{"number": 1, "note": "Brake late."}]))

        with (
            patch(_PATCH_IS_TASK_AVAILABLE, return_value=True),
            patch(_PATCH_CALL_TEXT_COMPLETION, return_value=response),
        ):
            drafts = await generate_coaching_drafts(corners, track_name="Test")

        assert len(drafts) == 2
        assert drafts[0].corner_number == 1
        assert drafts[0].coaching_note == "Brake late."
        assert drafts[1].corner_number == 2
        assert drafts[1].corner_name == "T2"
        assert drafts[1].coaching_note
