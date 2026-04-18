import math
import os
from typing import NamedTuple

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.messages import ModelMessage

load_dotenv()

model = AnthropicModel(
    "claude-sonnet-4-6",
    provider=AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY")),
)

agent = Agent(
    model=model,
    system_prompt=(
        "You are an expert structural engineering assistant with deep knowledge of "
        "ASCE 7-22, AISC Steel Construction Manual, ACI 318, and IBC building codes. "
        "Help engineers with structural calculations, code compliance questions, and design decisions. "
        "When performing calculations, always use the available tools to compute precise results — "
        "never guess or approximate numerical answers. "
        "Show your reasoning, state the code reference, and clearly present the results with units. "
        "If a question requires information you don't have (e.g., site-specific wind speed), ask for it."
    ),
)


class ExposureParams(NamedTuple):
    alpha: float
    zg: int
    Kh_15: float


EXPOSURE_PARAMS = {
    "B": ExposureParams(alpha=7.0, zg=1200, Kh_15=0.57),
    "C": ExposureParams(alpha=9.5, zg=900, Kh_15=0.85),
    "D": ExposureParams(alpha=11.5, zg=700, Kh_15=1.03),
}

MIN_HEIGHT_FT = 15.0
TOPOGRAPHIC_FACTOR = 1.0
DIRECTIONAL_FACTOR = 0.85
GROUND_ELEVATION_FACTOR = 1.0
GUST_FACTOR = 0.85
CP_WINDWARD = 0.8
CP_LEEWARD = -0.5


@agent.tool_plain
def calculate_wind_load(
    height_ft: float,
    basic_wind_speed_mph: float,
    exposure_category: str,
    internal_pressure_coefficient: float = 0.18,
) -> dict:
    """Calculate wind pressure per ASCE 7-22 Chapter 27 (Directional Procedure).

    Args:
        height_ft: Mean roof height of the building in feet.
        basic_wind_speed_mph: Design wind speed V in mph (from ASCE 7-22 Figure 26.5-1).
        exposure_category: Terrain exposure category: 'B', 'C', or 'D'.
        internal_pressure_coefficient: GCpi value; 0.18 for enclosed buildings (default).
    """
    cat = exposure_category.upper()
    if cat not in EXPOSURE_PARAMS:
        return {"error": f"Invalid exposure category '{exposure_category}'. Use B, C, or D."}

    params = EXPOSURE_PARAMS[cat]

    if height_ft <= MIN_HEIGHT_FT:
        Kz = params.Kh_15
    else:
        Kz = 2.01 * (height_ft / params.zg) ** (2 / params.alpha)

    qz = 0.00256 * Kz * TOPOGRAPHIC_FACTOR * DIRECTIONAL_FACTOR * GROUND_ELEVATION_FACTOR * (basic_wind_speed_mph ** 2)

    p_windward = qz * GUST_FACTOR * CP_WINDWARD - qz * internal_pressure_coefficient
    p_leeward = qz * GUST_FACTOR * CP_LEEWARD - qz * internal_pressure_coefficient
    net_pressure = p_windward - p_leeward

    return {
        "velocity_pressure_qz_psf": round(qz, 2),
        "Kz_factor": round(Kz, 3),
        "windward_pressure_psf": round(p_windward, 2),
        "leeward_pressure_psf": round(p_leeward, 2),
        "net_design_pressure_psf": round(net_pressure, 2),
        "code_reference": "ASCE 7-22 Chapter 27 (Directional Procedure)",
        "inputs": {
            "height_ft": height_ft,
            "wind_speed_mph": basic_wind_speed_mph,
            "exposure_category": cat,
            "GCpi": internal_pressure_coefficient,
        },
    }


E_STEEL_KSI = 29_000
E_WOOD_KSI = 1_600
ASSUMED_BEAM_DEPTH_IN = 12.0
DEFLECTION_LIMIT_DIVISOR = 360


@agent.tool_plain
def calculate_beam(
    span_ft: float,
    total_uniform_load_klf: float,
    material: str = "steel",
    allowable_stress_ksi: float = 24.0,
) -> dict:
    """Calculate beam moment, required section modulus, and max deflection under uniform load.

    Args:
        span_ft: Clear span of the beam in feet.
        total_uniform_load_klf: Total uniform load (dead + live) in kips per linear foot.
        material: 'steel' or 'wood'.
        allowable_stress_ksi: Allowable bending stress in ksi (default 24 ksi for A992 steel Fb).
    """
    w_klf = total_uniform_load_klf
    L_ft = span_ft

    M_max_kip_ft = (w_klf * L_ft ** 2) / 8
    M_max_kip_in = M_max_kip_ft * 12

    S_required_in3 = M_max_kip_in / allowable_stress_ksi

    E_ksi = E_STEEL_KSI if material.lower() == "steel" else E_WOOD_KSI
    I_estimated_in4 = S_required_in3 * (ASSUMED_BEAM_DEPTH_IN / 2)

    w_kip_in = w_klf / 12
    L_in = L_ft * 12
    delta_max_in = (5 * w_kip_in * L_in ** 4) / (384 * E_ksi * I_estimated_in4)

    deflection_limit_in = L_in / DEFLECTION_LIMIT_DIVISOR
    deflection_ok = delta_max_in <= deflection_limit_in

    return {
        "max_moment_kip_ft": round(M_max_kip_ft, 2),
        "max_moment_kip_in": round(M_max_kip_in, 2),
        "required_section_modulus_in3": round(S_required_in3, 2),
        "estimated_deflection_in": round(delta_max_in, 3),
        "deflection_limit_L360_in": round(deflection_limit_in, 3),
        "deflection_check": "PASS" if deflection_ok else "FAIL — increase section",
        "material": material,
        "allowable_stress_ksi": allowable_stress_ksi,
        "code_reference": "AISC ASD (steel) / NDS (wood) — simplified uniform load case",
        "inputs": {
            "span_ft": span_ft,
            "uniform_load_klf": total_uniform_load_klf,
        },
    }


@agent.tool_plain
def calculate_seismic_load(
    building_weight_kips: float,
    Ss: float,
    S1: float,
    site_class: str = "D",
    risk_category: str = "II",
) -> dict:
    """Calculate seismic base shear per ASCE 7-22 Equivalent Lateral Force procedure.

    Args:
        building_weight_kips: Effective seismic weight W of the building in kips.
        Ss: Mapped MCE spectral acceleration for short periods (from USGS/ASCE).
        S1: Mapped MCE spectral acceleration at 1-second period.
        site_class: ASCE 7-22 site class: 'A', 'B', 'C', 'D', 'E' (default D — stiff soil).
        risk_category: Building risk category: 'I', 'II', 'III', 'IV' (default II).
    """
    # Site coefficients Fa and Fv (ASCE 7-22 Tables 11.4-1 and 11.4-2, simplified)
    Fa_table = {"A": 0.8, "B": 0.9, "C": 1.3, "D": 1.6, "E": 2.4}
    Fv_table = {"A": 0.8, "B": 0.8, "C": 1.5, "D": 2.4, "E": 4.2}

    sc = site_class.upper()
    if sc not in Fa_table:
        return {"error": f"Invalid site class '{site_class}'. Use A–E."}

    Fa = Fa_table[sc]
    Fv = Fv_table[sc]

    SMS = Fa * Ss
    SM1 = Fv * S1
    SDS = (2 / 3) * SMS
    SD1 = (2 / 3) * SM1

    # Importance factor Ie
    Ie_map = {"I": 1.0, "II": 1.0, "III": 1.25, "IV": 1.5}
    rc = risk_category.upper()
    if rc not in Ie_map:
        return {"error": f"Invalid risk category '{risk_category}'. Use I, II, III, or IV."}
    Ie = Ie_map[rc]

    # Response modification coefficient R (assume ordinary steel moment frame as default)
    R = 3.5

    Cs = (SDS / (R / Ie))
    Cs_min = 0.044 * SDS * Ie
    Cs_max = SD1 / (1.0 * (R / Ie)) if SD1 > 0 else Cs
    Cs = max(min(Cs, Cs_max), Cs_min)

    V = Cs * building_weight_kips

    return {
        "SDS": round(SDS, 3),
        "SD1": round(SD1, 3),
        "seismic_response_coefficient_Cs": round(Cs, 4),
        "base_shear_V_kips": round(V, 2),
        "importance_factor_Ie": Ie,
        "response_modification_R": R,
        "code_reference": "ASCE 7-22 Section 12.8 — Equivalent Lateral Force Procedure",
        "note": "R=3.5 assumed (ordinary steel moment frame). Adjust R for your structural system.",
        "inputs": {
            "building_weight_kips": building_weight_kips,
            "Ss": Ss,
            "S1": S1,
            "site_class": sc,
            "risk_category": rc,
        },
    }


@agent.tool_plain
def calculate_footing(
    column_load_kips: float,
    allowable_soil_bearing_psf: float,
    footing_depth_ft: float = 3.0,
    concrete_unit_weight_pcf: float = 150.0,
    soil_unit_weight_pcf: float = 100.0,
) -> dict:
    """Size a square spread footing for a given column load and allowable soil bearing pressure.

    Args:
        column_load_kips: Unfactored (service) column axial load in kips.
        allowable_soil_bearing_psf: Allowable soil bearing capacity in pounds per square foot.
        footing_depth_ft: Depth of footing below finished grade in feet (default 3 ft).
        concrete_unit_weight_pcf: Unit weight of concrete in pcf (default 150 pcf).
        soil_unit_weight_pcf: Unit weight of soil overburden in pcf (default 100 pcf).
    """
    # Net allowable bearing = gross allowable - overburden pressure
    footing_thickness_ft = 1.5  # assumed footing thickness for self-weight estimate
    soil_depth_ft = footing_depth_ft - footing_thickness_ft

    overburden_psf = soil_unit_weight_pcf * soil_depth_ft + concrete_unit_weight_pcf * footing_thickness_ft
    net_allowable_psf = allowable_soil_bearing_psf - overburden_psf

    if net_allowable_psf <= 0:
        return {"error": "Net allowable bearing is zero or negative. Increase footing depth or soil bearing capacity."}

    required_area_sf = (column_load_kips * 1000) / net_allowable_psf
    side_length_ft = math.ceil(math.sqrt(required_area_sf) * 4) / 4  # round up to nearest 3"

    actual_area_sf = side_length_ft ** 2
    actual_pressure_psf = (column_load_kips * 1000) / actual_area_sf

    return {
        "required_footing_area_sf": round(required_area_sf, 2),
        "footing_size_ft": f"{side_length_ft} ft × {side_length_ft} ft (square)",
        "actual_soil_pressure_psf": round(actual_pressure_psf, 1),
        "net_allowable_bearing_psf": round(net_allowable_psf, 1),
        "overburden_pressure_psf": round(overburden_psf, 1),
        "code_reference": "ACI 318-19 Chapter 13 — Foundations (sizing only, reinforcement not included)",
        "note": "Reinforcement design and punching shear check required separately.",
        "inputs": {
            "column_load_kips": column_load_kips,
            "allowable_soil_bearing_psf": allowable_soil_bearing_psf,
            "footing_depth_ft": footing_depth_ft,
        },
    }


async def run_agent(user_message: str, history: list[ModelMessage]) -> str:
    """Thin wrapper around ``agent.run`` — exists as a patch point for tests."""
    result = await agent.run(user_message, message_history=history)
    return result.output
