"""Unit tests for the engineering calculation tools in agents.py.

These tests do not call the LLM — they exercise the pure-Python tool functions
directly, verifying that formulas produce correct results within engineering
tolerances.
"""
import pytest
from app.agents import (
    calculate_beam,
    calculate_footing,
    calculate_seismic_load,
    calculate_wind_load,
)


# ── Wind Load ─────────────────────────────────────────────────────────────────

class TestWindLoad:
    def test_returns_expected_keys(self):
        result = calculate_wind_load(
            height_ft=30, basic_wind_speed_mph=115, exposure_category="C"
        )
        assert "velocity_pressure_qz_psf" in result
        assert "Kz_factor" in result
        assert "windward_pressure_psf" in result
        assert "leeward_pressure_psf" in result
        assert "net_design_pressure_psf" in result
        assert "code_reference" in result

    def test_higher_wind_speed_raises_pressure(self):
        low = calculate_wind_load(40, 90, "C")
        high = calculate_wind_load(40, 130, "C")
        assert high["net_design_pressure_psf"] > low["net_design_pressure_psf"]

    def test_higher_building_raises_kz(self):
        short = calculate_wind_load(15, 115, "C")
        tall = calculate_wind_load(60, 115, "C")
        assert tall["Kz_factor"] > short["Kz_factor"]

    def test_exposure_d_higher_than_b(self):
        exp_b = calculate_wind_load(30, 115, "B")
        exp_d = calculate_wind_load(30, 115, "D")
        assert exp_d["velocity_pressure_qz_psf"] > exp_b["velocity_pressure_qz_psf"]

    def test_leeward_pressure_is_negative(self):
        result = calculate_wind_load(30, 115, "C")
        assert result["leeward_pressure_psf"] < 0

    def test_net_pressure_positive(self):
        result = calculate_wind_load(30, 115, "C")
        assert result["net_design_pressure_psf"] > 0

    def test_invalid_exposure_category_returns_error(self):
        result = calculate_wind_load(30, 115, "Z")
        assert "error" in result

    def test_exposure_b_kz_at_15ft_matches_table(self):
        # ASCE 7-22 Table 26.10-1: Kz at 15 ft, exposure B ≈ 0.57
        result = calculate_wind_load(15, 115, "B")
        assert abs(result["Kz_factor"] - 0.57) < 0.01

    def test_inputs_echoed_in_result(self):
        result = calculate_wind_load(40, 120, "C", internal_pressure_coefficient=0.18)
        assert result["inputs"]["height_ft"] == 40
        assert result["inputs"]["wind_speed_mph"] == 120
        assert result["inputs"]["exposure_category"] == "C"


# ── Beam ─────────────────────────────────────────────────────────────────────

class TestBeam:
    def test_returns_expected_keys(self):
        result = calculate_beam(24, 2.0)
        for key in ("max_moment_kip_ft", "required_section_modulus_in3",
                    "estimated_deflection_in", "deflection_check", "code_reference"):
            assert key in result

    def test_moment_formula(self):
        # M = wL²/8
        result = calculate_beam(span_ft=20, total_uniform_load_klf=1.0)
        expected_kip_ft = 1.0 * 20**2 / 8  # = 50 kip-ft
        assert abs(result["max_moment_kip_ft"] - expected_kip_ft) < 0.01

    def test_longer_span_increases_moment(self):
        short = calculate_beam(16, 2.0)
        long = calculate_beam(32, 2.0)
        assert long["max_moment_kip_ft"] > short["max_moment_kip_ft"]

    def test_heavier_load_increases_section_modulus(self):
        light = calculate_beam(20, 1.0)
        heavy = calculate_beam(20, 4.0)
        assert heavy["required_section_modulus_in3"] > light["required_section_modulus_in3"]

    def test_deflection_check_pass_for_light_load(self):
        result = calculate_beam(span_ft=12, total_uniform_load_klf=0.5, material="steel")
        assert result["deflection_check"] == "PASS"

    def test_deflection_check_fail_for_heavy_load(self):
        result = calculate_beam(span_ft=24, total_uniform_load_klf=3.0, material="steel")
        assert result["deflection_check"] == "FAIL — increase section"

    def test_section_modulus_scales_with_allowable_stress(self):
        high_fb = calculate_beam(20, 2.0, allowable_stress_ksi=30.0)
        low_fb = calculate_beam(20, 2.0, allowable_stress_ksi=15.0)
        assert low_fb["required_section_modulus_in3"] > high_fb["required_section_modulus_in3"]


# ── Seismic Load ──────────────────────────────────────────────────────────────

class TestSeismicLoad:
    def test_returns_expected_keys(self):
        result = calculate_seismic_load(500, 1.0, 0.5)
        for key in ("SDS", "SD1", "seismic_response_coefficient_Cs",
                    "base_shear_V_kips", "code_reference"):
            assert key in result

    def test_sds_formula(self):
        # SDS = (2/3) * Fa * Ss; Fa for site class D = 1.6
        result = calculate_seismic_load(1000, Ss=1.0, S1=0.5, site_class="D")
        expected_SDS = (2 / 3) * 1.6 * 1.0
        assert abs(result["SDS"] - expected_SDS) < 0.001

    def test_heavier_building_increases_base_shear(self):
        light = calculate_seismic_load(300, 1.0, 0.5)
        heavy = calculate_seismic_load(900, 1.0, 0.5)
        assert heavy["base_shear_V_kips"] > light["base_shear_V_kips"]

    def test_higher_ss_increases_base_shear(self):
        low = calculate_seismic_load(500, 0.5, 0.25)
        high = calculate_seismic_load(500, 1.5, 0.75)
        assert high["base_shear_V_kips"] > low["base_shear_V_kips"]

    def test_risk_category_iv_has_higher_ie(self):
        cat2 = calculate_seismic_load(500, 1.0, 0.5, risk_category="II")
        cat4 = calculate_seismic_load(500, 1.0, 0.5, risk_category="IV")
        assert cat4["importance_factor_Ie"] > cat2["importance_factor_Ie"]

    def test_invalid_site_class_returns_error(self):
        result = calculate_seismic_load(500, 1.0, 0.5, site_class="Z")
        assert "error" in result

    def test_base_shear_equals_cs_times_weight(self):
        result = calculate_seismic_load(400, 1.0, 0.5)
        expected_V = result["seismic_response_coefficient_Cs"] * 400
        assert abs(result["base_shear_V_kips"] - expected_V) < 0.01


# ── Footing ───────────────────────────────────────────────────────────────────

class TestFooting:
    def test_returns_expected_keys(self):
        result = calculate_footing(100, 2000)
        for key in ("required_footing_area_sf", "footing_size_ft",
                    "actual_soil_pressure_psf", "net_allowable_bearing_psf",
                    "code_reference"):
            assert key in result

    def test_heavier_load_requires_larger_footing(self):
        light = calculate_footing(80, 2000)
        heavy = calculate_footing(200, 2000)
        assert heavy["required_footing_area_sf"] > light["required_footing_area_sf"]

    def test_higher_bearing_allows_smaller_footing(self):
        soft = calculate_footing(120, 1500)
        firm = calculate_footing(120, 4000)
        assert firm["required_footing_area_sf"] < soft["required_footing_area_sf"]

    def test_actual_pressure_does_not_exceed_net_allowable(self):
        result = calculate_footing(120, 2000)
        assert result["actual_soil_pressure_psf"] <= result["net_allowable_bearing_psf"]

    def test_footing_size_string_format(self):
        result = calculate_footing(100, 2000)
        assert "ft × " in result["footing_size_ft"] or "ft ×" in result["footing_size_ft"]

    def test_overburden_reduces_net_allowable(self):
        result = calculate_footing(100, 2000, footing_depth_ft=3.0)
        assert result["net_allowable_bearing_psf"] < 2000

    def test_zero_net_bearing_returns_error(self):
        # Very shallow depth with very high unit weights can produce negative net bearing
        result = calculate_footing(100, 100, footing_depth_ft=3.0)
        assert "error" in result
