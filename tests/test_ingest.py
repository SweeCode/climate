"""Tests for OED ingestion — the pipeline where messy client data gets caught."""

from data.ingest import Severity, ingest_oed_locations


def _row(**over):
    base = {
        "LocNumber": "L1", "CountryCode": "DE",
        "Latitude": "50.94", "Longitude": "6.96",
        "BuildingTIV": "800000", "ContentsTIV": "150000", "BITIV": "50000",
        "LocDed": "10000", "LocLimit": "",
    }
    base.update(over)
    return base


def test_clean_row_loads_with_summed_tiv():
    locs, report = ingest_oed_locations([_row()])
    assert report.loaded == 1
    assert not report.errors
    assert locs[0].tiv == 1_000_000  # 800k + 150k + 50k
    assert locs[0].deductible == 10_000


def test_missing_coordinates_is_an_error_and_row_skipped():
    locs, report = ingest_oed_locations([_row(Latitude="", Longitude="")])
    assert locs == []
    assert report.loaded == 0
    assert any(i.field == "Latitude/Longitude" and i.severity is Severity.ERROR
               for i in report.errors)


def test_geocode_hook_rescues_missing_coordinates():
    locs, report = ingest_oed_locations(
        [_row(Latitude="", Longitude="")],
        geocode=lambda row: (48.85, 2.35),  # stand-in geocoder
    )
    assert report.loaded == 1
    assert (locs[0].lat, locs[0].lon) == (48.85, 2.35)


def test_zero_tiv_is_an_error():
    _, report = ingest_oed_locations([_row(BuildingTIV="0", ContentsTIV="", BITIV="")])
    assert report.loaded == 0
    assert any(i.field == "TIV" for i in report.errors)


def test_out_of_range_coordinate_is_an_error():
    _, report = ingest_oed_locations([_row(Latitude="999")])
    assert report.loaded == 0
    assert any("out of range" in i.message for i in report.errors)


def test_unknown_country_and_bad_terms_are_warnings_not_fatal():
    locs, report = ingest_oed_locations(
        [_row(CountryCode="US", LocDed="-5", LocLimit="-100")]
    )
    assert report.loaded == 1  # still usable
    fields = {i.field for i in report.warnings}
    assert {"CountryCode", "LocDed", "LocLimit"} <= fields
    assert locs[0].deductible == 0.0  # negative clamped
    assert locs[0].limit is None  # non-positive dropped


def test_report_summary_counts():
    rows = [_row(), _row(Latitude=""), _row(CountryCode="US")]
    _, report = ingest_oed_locations(rows)
    assert report.total_rows == 3
    assert report.loaded == 2  # one dropped for missing coords
    assert "2/3 locations loaded" in report.summary()
