"""Deduplication of superseded reprocessings.

Planetary Computer serves the same acquisition more than once when ESA has
reprocessed it, and over Al Massira those duplicates straddle the baseline-04.00
offset boundary -- so getting this wrong mixes corrected and uncorrected
reflectance inside a single mosaic.
"""

from __future__ import annotations

import datetime as dt

import pytest

from moroccowater.provenance import RunLog
from moroccowater.sentinel2 import dedupe_items, offsets_by_solar_day


class FakeItem:
    """Minimal stand-in: dedupe_items only touches id, datetime, properties."""

    def __init__(self, item_id: str, sensed: str, tile: str, baseline: str):
        self.id = item_id
        self.datetime = dt.datetime.fromisoformat(sensed).replace(tzinfo=dt.UTC)
        self.properties = {"s2:mgrs_tile": tile, "s2:processing_baseline": baseline}
        self.assets: dict = {}


# The real pair found over Al Massira on 2021-12-12.
def _real_duplicate_pair() -> list[FakeItem]:
    return [
        FakeItem("S2B_..._T29SPS_20230125T204851", "2021-12-12T11:13:49", "29SPS", "04.00"),
        FakeItem("S2B_..._T29SPS_20211213T050422", "2021-12-12T11:13:49", "29SPS", "03.00"),
        FakeItem("S2B_..._T29SPR_20230125T200249", "2021-12-12T11:13:49", "29SPR", "04.00"),
        FakeItem("S2B_..._T29SPR_20211213T060529", "2021-12-12T11:13:49", "29SPR", "03.00"),
    ]


def test_keeps_highest_baseline_per_tile_and_sensing_time():
    kept = dedupe_items(_real_duplicate_pair(), RunLog("t"))
    assert len(kept) == 2  # one per tile
    assert {i.properties["s2:processing_baseline"] for i in kept} == {"04.00"}
    assert {i.properties["s2:mgrs_tile"] for i in kept} == {"29SPS", "29SPR"}


def test_dedupe_resolves_the_mixed_offset_conflict():
    """Without dedup these items trip the radiometry guard; with it they don't."""
    items = _real_duplicate_pair()
    with pytest.raises(ValueError, match="mixed scale/offset"):
        offsets_by_solar_day(items, RunLog("t"))

    per_day = offsets_by_solar_day(dedupe_items(items, RunLog("t")), RunLog("t"))
    assert len(per_day) == 1
    assert per_day.loc[0, "offset"] == -1000.0  # baseline 04.00 wins


def test_distinct_acquisitions_are_not_deduplicated():
    items = [
        FakeItem("a", "2023-03-01T11:00:00", "29SPS", "05.09"),
        FakeItem("b", "2023-03-06T11:00:00", "29SPS", "05.09"),  # different day
        FakeItem("c", "2023-03-01T11:00:00", "29SPR", "05.09"),  # different tile
    ]
    assert len(dedupe_items(items, RunLog("t"))) == 3


def test_unparseable_baseline_loses_to_a_real_one():
    items = [
        FakeItem("good", "2023-03-01T11:00:00", "29SPS", "05.09"),
        FakeItem("bad", "2023-03-01T11:00:00", "29SPS", "N/A"),
    ]
    kept = dedupe_items(items, RunLog("t"))
    assert [i.id for i in kept] == ["good"]


def test_output_is_sorted_by_acquisition_time():
    items = [
        FakeItem("late", "2023-06-01T11:00:00", "29SPS", "05.09"),
        FakeItem("early", "2023-01-01T11:00:00", "29SPS", "05.09"),
    ]
    assert [i.id for i in dedupe_items(items, RunLog("t"))] == ["early", "late"]


def test_date_rule_would_misclassify_a_reprocessed_2021_scene():
    """Why the baseline is read instead of the acquisition date: this scene was
    sensed in Dec 2021 but reprocessed under 04.00, so it DOES carry the offset
    even though a date cut at 2022-01-25 would say otherwise."""
    reprocessed = FakeItem(
        "S2B_..._T29SPS_20230125T204851", "2021-12-12T11:13:49", "29SPS", "04.00"
    )
    per_day = offsets_by_solar_day([reprocessed], RunLog("t"))
    assert per_day.loc[0, "offset"] == -1000.0
    assert per_day.loc[0, "how"] == "s2:processing_baseline=04.00"
