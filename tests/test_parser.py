"""Tests for cataclysm.parser."""

from __future__ import annotations

import io

import pytest

from cataclysm.parser import (
    MAX_ACCURACY_M,
    MIN_SATELLITES,
    ParsedSession,
    SessionMetadata,
    _parse_metadata,
    parse_racechrono_csv,
)


class TestParseMetadata:
    def test_extracts_track_name(self) -> None:
        lines = [
            "This file is created using RaceChrono v9.1.3 ( http://racechrono.com/ ).\n",
            "Format,3\n",
            'Session title,"Barber"\n',
            "Session type,Lap timing\n",
            'Track name,"Barber Motorsports Park"\n',
            "Driver name,\n",
            "Created,21/02/2026,19:32\n",
            "Note,\n",
        ]
        meta = _parse_metadata(lines)
        assert meta.track_name == "Barber Motorsports Park"

    def test_extracts_version(self) -> None:
        lines = [
            "This file is created using RaceChrono v9.1.3 ( http://racechrono.com/ ).\n",
            "Format,3\n",
            'Session title,"X"\n',
            "Session type,Lap timing\n",
            'Track name,"X"\n',
            "Driver name,\n",
            "Created,01/01/2026,12:00\n",
            "Note,\n",
        ]
        meta = _parse_metadata(lines)
        assert meta.racechrono_version == "v9.1.3"

    def test_extracts_date(self) -> None:
        lines = [
            "This file is created using RaceChrono v9.1.3.\n",
            "Format,3\n",
            'Session title,"X"\n',
            "Session type,Lap timing\n",
            'Track name,"X"\n',
            "Driver name,\n",
            "Created,21/02/2026,19:32\n",
            "Note,\n",
        ]
        meta = _parse_metadata(lines)
        assert "21/02/2026" in meta.session_date
        assert "19:32" in meta.session_date

    def test_handles_missing_version(self) -> None:
        lines = [
            "Some other header line\n",
            "Format,3\n",
            'Session title,"X"\n',
            "Session type,Lap timing\n",
            'Track name,"Y"\n',
            "Driver name,\n",
            "Created,01/01/2026\n",
            "Note,\n",
        ]
        meta = _parse_metadata(lines)
        assert meta.racechrono_version == ""


class TestParseRacechronoCsv:
    def test_parses_from_file(self, racechrono_csv_file: str) -> None:
        result = parse_racechrono_csv(racechrono_csv_file)
        assert isinstance(result, ParsedSession)
        assert isinstance(result.metadata, SessionMetadata)
        assert not result.data.empty

    def test_parses_from_file_object(self, racechrono_csv_text: str) -> None:
        f = io.StringIO(racechrono_csv_text)
        result = parse_racechrono_csv(f)
        assert not result.data.empty

    def test_metadata_populated(self, racechrono_csv_file: str) -> None:
        result = parse_racechrono_csv(racechrono_csv_file)
        assert result.metadata.track_name == "Test Circuit"
        assert "22/02/2026" in result.metadata.session_date

    def test_correct_columns(self, racechrono_csv_file: str) -> None:
        result = parse_racechrono_csv(racechrono_csv_file)
        expected = {
            "timestamp",
            "lap_number",
            "elapsed_time",
            "distance_m",
            "accuracy_m",
            "altitude_m",
            "heading_deg",
            "lat",
            "lon",
            "satellites",
            "speed_mps",
            "lateral_g",
            "longitudinal_g",
            "x_acc_g",
            "y_acc_g",
            "z_acc_g",
            "yaw_rate_dps",
        }
        assert expected == set(result.data.columns)

    def test_filters_bad_accuracy(self, racechrono_csv_file: str) -> None:
        result = parse_racechrono_csv(racechrono_csv_file)
        assert (result.data["accuracy_m"] <= MAX_ACCURACY_M).all()

    def test_filters_low_satellites(self, racechrono_csv_file: str) -> None:
        result = parse_racechrono_csv(racechrono_csv_file)
        assert (result.data["satellites"] >= MIN_SATELLITES).all()

    def test_speed_non_negative(self, racechrono_csv_file: str) -> None:
        result = parse_racechrono_csv(racechrono_csv_file)
        assert (result.data["speed_mps"] >= 0).all()

    def test_sorted_by_elapsed_time(self, racechrono_csv_file: str) -> None:
        result = parse_racechrono_csv(racechrono_csv_file)
        assert result.data["elapsed_time"].is_monotonic_increasing

    def test_out_lap_excluded(self, racechrono_csv_file: str) -> None:
        """Out-lap rows (no lap_number) should still be in data but with NaN lap_number."""
        result = parse_racechrono_csv(racechrono_csv_file)
        # Out-lap rows have NaN lap_number, they're kept in the DataFrame
        # but engine.py will filter them out during lap splitting
        assert result.data["lap_number"].notna().any()

    def test_rejects_wrong_column_count(self, tmp_path: object) -> None:
        """CSV with too few columns should raise ValueError."""
        import pathlib

        p = pathlib.Path(str(tmp_path)) / "bad.csv"
        lines = [
            "RaceChrono v9.1.3\n",
            "Format,3\n",
            'Session title,"X"\n',
            "Session type,Lap timing\n",
            'Track name,"X"\n',
            "Driver name,\n",
            "Created,01/01/2026\n",
            "Note,\n",
            "\n",
            "a,b,c\n",
            "1,2,3\n",
            "x,y,z\n",
            "1.0,2.0,3.0\n",
        ]
        p.write_text("".join(lines))
        with pytest.raises(ValueError, match="columns"):
            parse_racechrono_csv(str(p))
