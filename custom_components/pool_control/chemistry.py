"""Water chemistry calculations.

All functions in this module are pure and independent of Home Assistant.
"""

from __future__ import annotations

from bisect import bisect_right

# ORP set points (mV) for a given free chlorine level (ppm) and pH.
# Source: PoolRx Worldwide ORP/free chlorine correlation chart.
# Missing values (ORP above the chart range) are filled with the nearest
# available value at the same chlorine level, which yields a conservative
# (lower) set point.
PH_AXIS: tuple[float, ...] = (7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8.0)
_RAW_ORP_TABLE: dict[float, tuple[int | None, ...]] = {
    0.5: (735, 725, 720, 712, 704, 695, 687, 680, 675, 668, 662),
    1.0: (760, 750, 742, 734, 725, 716, 709, 703, 695, 689, 684),
    1.5: (772, 765, 756, 748, 738, 731, 722, 715, 708, 702, 697),
    2.0: (780, 772, 763, 756, 748, 740, 732, 724, 717, 712, 705),
    2.5: (788, 780, 772, 763, 754, 746, 738, 732, 725, 718, 714),
    3.0: (794, 785, 778, 769, 761, 753, 745, 737, 731, 724, 719),
    3.5: (800, 792, 782, 774, 765, 758, 750, 742, 735, 729, 724),
    4.0: (None, 798, 786, 778, 770, 762, 754, 746, 739, 734, 728),
    4.5: (None, None, 792, 782, 774, 766, 757, 751, 743, 736, 733),
    5.0: (None, None, 798, 785, 778, 769, 761, 754, 746, 741, 736),
}


def _fill_row(row: tuple[int | None, ...]) -> tuple[float, ...]:
    first = next(value for value in row if value is not None)
    filled: list[float] = []
    for value in row:
        filled.append(float(first if value is None else value))
    return tuple(filled)


CHLORINE_AXIS: tuple[float, ...] = tuple(sorted(_RAW_ORP_TABLE))
ORP_TABLE: tuple[tuple[float, ...], ...] = tuple(
    _fill_row(_RAW_ORP_TABLE[chlorine]) for chlorine in CHLORINE_AXIS
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _axis_position(axis: tuple[float, ...], value: float) -> tuple[int, float]:
    """Return the lower index and interpolation fraction of value on axis."""
    value = _clamp(value, axis[0], axis[-1])
    index = min(bisect_right(axis, value) - 1, len(axis) - 2)
    fraction = (value - axis[index]) / (axis[index + 1] - axis[index])
    return index, fraction


def orp_target(ph: float, chlorine_ppm: float) -> float:
    """Return the ORP set point in mV for the given pH and free chlorine target.

    Values are interpolated bilinearly. Inputs outside the chart are clamped
    to its edges.
    """
    row, row_frac = _axis_position(CHLORINE_AXIS, chlorine_ppm)
    col, col_frac = _axis_position(PH_AXIS, ph)
    low = ORP_TABLE[row]
    high = ORP_TABLE[row + 1]
    low_value = low[col] + (low[col + 1] - low[col]) * col_frac
    high_value = high[col] + (high[col + 1] - high[col]) * col_frac
    return round(low_value + (high_value - low_value) * row_frac, 1)


def ph_dose_ml(volume_m3: float, ph_drop: float, product_dose: float) -> float:
    """Return the amount of pH minus product (ml) needed for a pH drop.

    product_dose is the manufacturer's dosage in ml per 10 m3 per 0.1 pH.
    """
    if ph_drop <= 0:
        return 0.0
    return ph_drop / 0.1 * product_dose * volume_m3 / 10.0


def ph_drop_for_dose(volume_m3: float, dose_ml: float, product_dose: float) -> float:
    """Return the expected pH drop for an amount of product (ml)."""
    if dose_ml <= 0 or volume_m3 <= 0 or product_dose <= 0:
        return 0.0
    return dose_ml / (product_dose * volume_m3 / 10.0) * 0.1


def product_dose_from_observation(volume_m3: float, dose_ml: float, ph_drop: float) -> float | None:
    """Return the observed product dose (ml per 10 m3 per 0.1 pH)."""
    if dose_ml <= 0 or ph_drop <= 0 or volume_m3 <= 0:
        return None
    return dose_ml / (ph_drop / 0.1) / (volume_m3 / 10.0)


def pump_seconds_for_dose(dose_ml: float, rate_ml_per_min: float) -> float:
    """Return the run time (s) of a dosing pump for a given amount."""
    if dose_ml <= 0 or rate_ml_per_min <= 0:
        return 0.0
    return dose_ml / rate_ml_per_min * 60.0


def dose_for_pump_seconds(seconds: float, rate_ml_per_min: float) -> float:
    """Return the amount (ml) delivered by a dosing pump in a given time."""
    if seconds <= 0 or rate_ml_per_min <= 0:
        return 0.0
    return seconds * rate_ml_per_min / 60.0


def salt_correction_kg(volume_m3: float, current_ppm: float, target_ppm: float) -> float:
    """Return the amount of salt (kg) needed to reach the target concentration."""
    if target_ppm <= current_ppm:
        return 0.0
    return (target_ppm - current_ppm) * volume_m3 / 1000.0


def salt_dilution_m3(volume_m3: float, current_ppm: float, target_ppm: float) -> float:
    """Return the volume of fresh water (m3) to exchange to lower salt content."""
    if current_ppm <= target_ppm or current_ppm <= 0:
        return 0.0
    return volume_m3 * (1 - target_ppm / current_ppm)


def filtration_hours(water_temp: float, divisor: float, minimum: float, maximum: float) -> float:
    """Return the daily filtration time (h) for a water temperature."""
    hours = water_temp / divisor if divisor > 0 else maximum
    return round(_clamp(hours, minimum, maximum), 2)
