"""Tests for the chemistry calculations."""

from __future__ import annotations

import pytest

from custom_components.pool_control import chemistry


@pytest.mark.parametrize(
    ("ph", "chlorine", "expected"),
    [
        (7.2, 2.0, 763),
        (7.4, 2.0, 748),
        (7.0, 0.5, 735),
        (8.0, 5.0, 736),
        (7.25, 2.0, 759.5),
        (7.2, 2.25, 767.5),
        (6.5, 2.0, 780),
        (8.5, 2.0, 705),
        (7.4, 0.1, 704),
        (7.4, 9.0, 778),
    ],
)
def test_orp_target(ph: float, chlorine: float, expected: float) -> None:
    assert chemistry.orp_target(ph, chlorine) == pytest.approx(expected)


def test_orp_target_fills_missing_cells() -> None:
    # Missing chart values use the nearest available value of the row.
    assert chemistry.orp_target(7.0, 5.0) == 798
    assert chemistry.orp_target(7.0, 4.0) == 798


def test_orp_target_rises_with_ph_and_chlorine() -> None:
    assert chemistry.orp_target(7.2, 2.0) > chemistry.orp_target(7.6, 2.0)
    assert chemistry.orp_target(7.4, 3.0) > chemistry.orp_target(7.4, 1.0)


def test_ph_dose_roundtrip() -> None:
    dose = chemistry.ph_dose_ml(17.2, 0.1, 300)
    assert dose == pytest.approx(516)
    assert chemistry.ph_drop_for_dose(17.2, dose, 300) == pytest.approx(0.1)
    assert chemistry.product_dose_from_observation(17.2, dose, 0.1) == pytest.approx(300)


@pytest.mark.parametrize(
    ("func", "args"),
    [
        (chemistry.ph_dose_ml, (17.2, -0.1, 300)),
        (chemistry.ph_drop_for_dose, (17.2, 0, 300)),
        (chemistry.pump_seconds_for_dose, (0, 20)),
        (chemistry.dose_for_pump_seconds, (60, 0)),
        (chemistry.salt_correction_kg, (17.2, 4000, 3500)),
        (chemistry.salt_dilution_m3, (17.2, 3000, 3500)),
    ],
)
def test_zero_results(func, args) -> None:
    assert func(*args) == 0


def test_product_dose_from_observation_invalid() -> None:
    assert chemistry.product_dose_from_observation(17.2, 100, 0) is None


def test_pump_conversions() -> None:
    assert chemistry.pump_seconds_for_dose(21, 21) == pytest.approx(60)
    assert chemistry.dose_for_pump_seconds(30, 21) == pytest.approx(10.5)


def test_salt() -> None:
    assert chemistry.salt_correction_kg(17.2, 2500, 3500) == pytest.approx(17.2)
    assert chemistry.salt_dilution_m3(17.2, 4000, 3500) == pytest.approx(2.15)


@pytest.mark.parametrize(
    ("temp", "expected"), [(26, 12.0), (24, 12.0), (20, 10.0), (10, 5.0), (2, 2.0)]
)
def test_filtration_hours(temp: float, expected: float) -> None:
    assert chemistry.filtration_hours(temp, 2.0, 2.0, 12.0) == expected


def test_filtration_hours_invalid_divisor() -> None:
    assert chemistry.filtration_hours(20, 0, 2, 12) == 12


def test_saturation_index() -> None:
    assert chemistry.saturation_index(7.4, 26, 250, 100, tds_ppm=3500) == pytest.approx(
        -0.22, abs=0.01
    )
    balanced = chemistry.saturation_index(7.6, 28, 300, 120, tds_ppm=3500)
    assert balanced is not None
    assert balanced > 0
    with_cya = chemistry.saturation_index(7.4, 26, 250, 100, cyanuric_acid_ppm=60, tds_ppm=3500)
    assert with_cya is not None
    assert with_cya < -0.22
    assert chemistry.saturation_index(7.4, 26, 0, 100) is None
    assert chemistry.saturation_index(7.4, 26, 250, 10, cyanuric_acid_ppm=60) is None
