"""DPE labelling rules, shared by features (harmonise) and monitoring (simulate)."""
CLASSES = list("ABCDEFG")
EP_LIMITS = [70, 110, 180, 250, 330, 420]   # primary energy, kWh/m²/yr: upper bound of A..F
GES_LIMITS = [6, 11, 30, 50, 70, 100]       # CO2, kg/m²/yr: upper bound of A..F
BASE_COEF = 1.9                             # coefficient behind ADEME's *_pef19 columns


def class_index(ep: str, ges: str) -> str:
    """SQL: label index 1 (A) .. 7 (G) = worst of energy and CO2 thresholds (2021 method)."""
    e = " + ".join(f"({ep} > {t})::INT" for t in EP_LIMITS)
    g = " + ".join(f"(coalesce({ges}, 0) > {t})::INT" for t in GES_LIMITS)
    return f"(1 + greatest({e}, {g}))"


def harmonised_sql(coef: float, elec_ids: list[int]) -> tuple[str, str]:
    """SQL for (label ordinal, primary energy) of each DPE under electricity coefficient `coef`.
    At the base coefficient, ADEME's own harmonised values are used unchanged."""
    
    base_cls = f"list_position({CLASSES}, coalesce(classe_dpe_pef19, classe_dpe))"
    base_ep = "coalesce(ep_m2_pef19, ep_m2)"
    if abs(coef - BASE_COEF) < 1e-9 or not elec_ids:
        return base_cls, base_ep
    ids = ",".join(map(str, elec_ids))
    ep = f"{base_ep} * {coef} / {BASE_COEF}"
    is_elec = f"energie_id IN ({ids}) AND {base_ep} IS NOT NULL"
    return (f"CASE WHEN {is_elec} THEN {class_index(ep, 'ges_m2')} ELSE {base_cls} END",
            f"CASE WHEN {is_elec} THEN {ep} ELSE {base_ep} END")