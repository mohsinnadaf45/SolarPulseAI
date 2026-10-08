"""
backend/tests/test_diagnosis_service.py

Unit tests for AI root-cause diagnosis engine:
- Inverter error code matching
- Multi-modal telemetry reasoning
- Technician remediation step generation
- Loss impact valuation
"""

import pytest
from app.services.diagnosis_service import (
    diagnose_root_cause,
    get_root_cause_taxonomy,
    _match_error_code,
)


def test_taxonomy_retrieval():
    """Verify diagnostic taxonomy contains all critical categories."""
    taxonomy = get_root_cause_taxonomy()
    assert len(taxonomy) >= 8

    categories = [t.category for t in taxonomy]
    assert "INVERTER_TRIP_OVERTEMP" in categories
    assert "GROUND_FAULT_INSULATION" in categories
    assert "DC_STRING_FAULT" in categories
    assert "ARC_FAULT_AFCI" in categories
    assert "GRID_CURTAILMENT_OVERVOLTAGE" in categories
    assert "SOILING_DEGRADATION" in categories
    assert "INVERTER_CLIPPING_SATURATION" in categories


def test_error_code_matching_known_codes():
    """Verify standard multi-vendor inverter error codes match expected categories."""
    assert _match_error_code("F056")[0] == "INVERTER_TRIP_OVERTEMP"
    assert _match_error_code("E001")[0] == "INVERTER_TRIP_OVERTEMP"
    assert _match_error_code("F034")[0] == "GROUND_FAULT_INSULATION"
    assert _match_error_code("ISO_FAULT")[0] == "GROUND_FAULT_INSULATION"
    assert _match_error_code("F063")[0] == "ARC_FAULT_AFCI"
    assert _match_error_code("AFCI_FAULT")[0] == "ARC_FAULT_AFCI"
    assert _match_error_code("F012")[0] == "DC_STRING_FAULT"
    assert _match_error_code("F021")[0] == "GRID_CURTAILMENT_OVERVOLTAGE"
    assert _match_error_code("F077")[0] == "MPPT_TRACKER_FAILURE"
    assert _match_error_code("F088")[0] == "COMMUNICATION_SCADA_LOSS"


def test_diagnosis_from_inverter_error_code():
    """Verify full diagnostic response generated from error code."""
    res = diagnose_root_cause(
        plant_id=1,
        plant_name="Bhadla Solar Park",
        capacity_kw=50000.0,
        inverter_error_code="F034",
        expected_power_kw=42000.0,
        actual_power_kw=28000.0,
    )

    assert res.root_cause_category == "GROUND_FAULT_INSULATION"
    assert "Ground Fault" in res.root_cause_title
    assert res.confidence_score >= 90.0
    assert res.urgency_level == "CRITICAL"
    assert res.estimated_loss_kw == 14000.0
    assert res.financial_impact_per_day > 1000.0
    assert res.safety_warning is not None
    assert len(res.technician_steps) >= 3

    # Check tools in technician steps
    tool_list = [tool for step in res.technician_steps for tool in step.required_tools]
    assert any("Megohmmeter" in t or "Insulation" in t for t in tool_list)


def test_diagnosis_from_telemetry_signature_overtemp():
    """Verify telemetry-based diagnosis when error code is absent but temperature is high."""
    res = diagnose_root_cause(
        plant_id=1,
        capacity_kw=1000.0,
        expected_power_kw=900.0,
        actual_power_kw=450.0,
        irradiance_w_m2=850.0,
        temperature_c=42.0,
        module_temp_c=58.0,
        alert_message="Sudden 50% power drop during midday peak",
    )

    assert res.root_cause_category == "INVERTER_TRIP_OVERTEMP"
    assert res.urgency_level == "HIGH"
    assert res.confidence_score >= 80.0
    assert res.estimated_loss_kw == 450.0


def test_diagnosis_from_soiling_deficit():
    """Verify soiling diagnosis on gradual clear-sky deficit."""
    res = diagnose_root_cause(
        plant_id=1,
        capacity_kw=1000.0,
        expected_power_kw=800.0,
        actual_power_kw=680.0,  # 15% shortfall
        irradiance_w_m2=750.0,
        days_since_cleaning=18.0,
        alert_message="Sub-array soiling deficit against clear-sky baseline",
    )

    assert res.root_cause_category == "SOILING_DEGRADATION"
    assert res.urgency_level == "MEDIUM"
    assert "Soiling" in res.root_cause_title


def test_diagnosis_from_ac_clipping():
    """Verify clipping diagnosis when power matches inverter export ceiling."""
    res = diagnose_root_cause(
        plant_id=1,
        capacity_kw=1000.0,
        expected_power_kw=880.0,
        actual_power_kw=850.0,
        irradiance_w_m2=950.0,
        alert_message="Inverter AC clipping detected at 850 kW export threshold",
    )

    assert res.root_cause_category == "INVERTER_CLIPPING_SATURATION"
    assert res.urgency_level == "LOW"
    assert res.safety_warning is not None
