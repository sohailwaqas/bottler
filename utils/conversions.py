"""
utils/conversions.py — the ONE place 8oz / ml / raw-case math happens.

Every module that needs an 8oz-equivalent figure (targets, incentives,
loss quotas) must call into this file rather than re-implementing the
`1 ml = 0.00017612 8oz` constant inline. This keeps the conversion
auditable and trivially testable.
"""
import config

ML_TO_8OZ = config.ML_TO_8OZ
OZ8_IN_ML = 1 / ML_TO_8OZ  # ~5,677.5 ml per 8oz-unit... (kept for reference only)


def ml_to_8oz(ml: float) -> float:
    """Convert a raw ml volume into 8oz-equivalent units."""
    return ml * ML_TO_8OZ


def cases_to_8oz(num_cases: float, units_per_case: int, unit_volume_ml: float) -> float:
    """
    Convert a quantity of cases into 8oz-equivalent volume.
    num_cases        : number of cases
    units_per_case    : bottles/cans per case
    unit_volume_ml     : volume of a single unit in ml
    """
    total_ml = num_cases * units_per_case * unit_volume_ml
    return ml_to_8oz(total_ml)


def package_to_ml(package: str) -> float:
    """Best-effort parse of a package label like '500 ML PET' -> 500.0 ml."""
    import re
    m = re.search(r"([\d.]+)\s*(ml|l)\b", package.lower())
    if not m:
        return 0.0
    val, unit = float(m.group(1)), m.group(2)
    return val * 1000 if unit == "l" else val


def sku_row_to_8oz(quantity_cases: float, sku_row) -> float:
    """Convenience wrapper: given a SKU row (with units_per_case & package), return 8oz."""
    unit_ml = package_to_ml(sku_row["package"])
    return cases_to_8oz(quantity_cases, sku_row["units_per_case"], unit_ml)


def raw_case_1l_pet_equivalent(quantity_cases: float, units_per_case: int, unit_volume_ml: float) -> float:
    """
    Normalize any brand/package case quantity into 1L-PET-equivalent raw
    cases, per the spec's "1 case of 1L PET = 1 case of any brand/package"
    raw-case normalization. We do this via the 8oz-equivalent volume so the
    normalization is exact regardless of pack size, then re-express it in
    1L-PET case units (12 x 1000ml per the demo catalogue's own 1L PET case).
    """
    total_8oz = cases_to_8oz(quantity_cases, units_per_case, unit_volume_ml)
    one_l_pet_case_8oz = cases_to_8oz(1, 12, 1000.0)
    return total_8oz / one_l_pet_case_8oz if one_l_pet_case_8oz else 0.0


def incentive_for_achievement(achieved_8oz: float, target_8oz: float, incentive_per_case: float,
                               units_per_case: int = 12, unit_volume_ml: float = 1000.0) -> float:
    """
    Very small helper: incentive is paid per RAW CASE (not per 8oz), so we
    convert the achieved 8oz volume back into raw-case units before
    multiplying by the incentive rate. Only called when target is met.
    """
    if achieved_8oz < target_8oz:
        return 0.0
    one_case_8oz = cases_to_8oz(1, units_per_case, unit_volume_ml)
    raw_cases = achieved_8oz / one_case_8oz if one_case_8oz else 0
    return raw_cases * incentive_per_case
