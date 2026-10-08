"""
app/services/diagnosis_service.py

AI-Based Root-Cause Diagnostic Engine for solar photovoltaic plants and inverters.
Diagnoses equipment trips, string disconnects, ground faults, soiling, arc faults,
and grid curtailment using multi-vendor error codes, telemetry signatures, and physics context.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.alert import AnomalyAlert
from app.models.diagnosis import DiagnosisRecord
from app.models.plant import Plant
from app.models.scada import ScadaReading
from app.schemas.diagnosis import (
    DiagnosisRequest,
    DiagnosisResponse,
    RootCauseTaxonomyItem,
    TechnicianStep,
)

logger = get_logger(__name__)

# Standard Commercial PPA Energy Rate ($/kWh)
DEFAULT_PPA_TARIFF_PER_KWH = 0.08
DEFAULT_PEAK_SUN_HOURS = 5.5


# ── Diagnostic Knowledge Base ─────────────────────────────────────────────────

DIAGNOSTIC_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "INVERTER_TRIP_OVERTEMP": {
        "title": "Inverter Thermal Derating / Cooling Fan Failure",
        "category": "INVERTER_TRIP_OVERTEMP",
        "urgency": "HIGH",
        "description": "Internal IGBT heatsink or cabinet ambient temperature exceeded safe threshold, triggering thermal derate or safety shutdown.",
        "common_codes": ["F056", "E001", "W011", "OVERTEMP", "TEMP_DERATE", "FAN_FAULT"],
        "safety_warning": "CAUTION: Inverter cabinet and heatsink surfaces may be in excess of 85°C. Allow thermal cool-down before servicing internal components.",
        "preventative_advice": "Implement quarterly filter mat replacement and thermal camera inspections during peak irradiance hours.",
        "steps": [
            {
                "step_number": 1,
                "action": "Inspect external cabinet air intake and exhaust louvers for dust accumulation or blocked airflow.",
                "required_tools": ["Visual inspection kit", "Handheld anemometer"],
                "safety_note": "Keep face clear of high-velocity exhaust vents.",
            },
            {
                "step_number": 2,
                "action": "Test cooling fan rotation and tachometer feedback signals on fan banks A and B.",
                "required_tools": ["Digital multimeter", "Infrared tachometer"],
                "safety_note": "Lockout/Tagout (LOTO) auxiliary fan power prior to manual blade spin check.",
            },
            {
                "step_number": 3,
                "action": "Perform thermal imaging scan on IGBT power modules and heat pipe exchangers to detect localized hot spots.",
                "required_tools": ["Calibrated FLIR thermal imaging camera", "Class 0 electrical gloves"],
                "safety_note": "Wear arc flash shield and Category 2 PPE when cabinet door is opened.",
            },
            {
                "step_number": 4,
                "action": "Clear fan fault latch in inverter firmware menu and initiate controlled ramp-up.",
                "required_tools": ["Manufacturer service software / Modbus portal"],
                "safety_note": "Monitor heatsink temperature gradient during reconnection.",
            },
        ],
    },
    "GROUND_FAULT_INSULATION": {
        "title": "DC Ground Fault / Low Insulation Resistance (Riso)",
        "category": "GROUND_FAULT_INSULATION",
        "urgency": "CRITICAL",
        "description": "Insulation resistance between DC live conductors and earth dropped below statutory threshold (typically < 1 MOhm), usually after precipitation or condensation.",
        "common_codes": ["F034", "E002", "ISO_FAULT", "LOW_RISO", "GROUND_FAULT", "EARTH_LEAKAGE"],
        "safety_warning": "DANGER: HIGH SHOCK HAZARD. DC bus may remain energized relative to ground. Treat all module frames and conduit as potentially live.",
        "preventative_advice": "Inspect cable trays and drip loops in water-pooling zones; reseal submerged MC4 connector joints with IP68 heat-shrink boots.",
        "steps": [
            {
                "step_number": 1,
                "action": "Isolate the faulted inverter via DC disconnect switch and verify zero current flow.",
                "required_tools": ["1000V DC rated clamp meter", "Category 3 Arc Flash PPE"],
                "safety_note": "Never open DC fuses under load.",
            },
            {
                "step_number": 2,
                "action": "Measure DC insulation resistance between positive/negative poles to ground at each combiner box branch.",
                "required_tools": ["1000V calibrated Megohmmeter (Insulation Resistance Tester)"],
                "safety_note": "Ensure test leads are grounded before initiating high-voltage pulse.",
            },
            {
                "step_number": 3,
                "action": "Perform sectional half-string disconnection to isolate the damaged module, crushed cable, or pinched conduit.",
                "required_tools": ["MC4 disconnect tools", "Multimeter"],
                "safety_note": "Beware of capacitive discharge stored in array cabling.",
            },
            {
                "step_number": 4,
                "action": "Replace pinched cable harness / compromised junction box and retest insulation resistance to > 50 MOhms.",
                "required_tools": ["Heat gun", "IP68 cable splice kit"],
                "safety_note": "Verify continuity to equipment grounding conductor (EGC).",
            },
        ],
    },
    "DC_STRING_FAULT": {
        "title": "DC String Open-Circuit / Blown Combiner Fuse",
        "category": "DC_STRING_FAULT",
        "urgency": "HIGH",
        "description": "One or more DC series strings are offline or disconnected, resulting in step-down capacity loss while operating voltages appear near nominal.",
        "common_codes": ["F012", "E003", "STRING_OC", "FUSE_BLOWN", "OPEN_CIRCUIT", "COMBINER_FAIL"],
        "safety_warning": "WARNING: Potential DC arc flash. Ensure string current is verified with a clamp meter before pulling ganged fuseholders.",
        "preventative_advice": "Check string current balance quarterly via SCADA string monitoring to spot early degradation before fuse rupture.",
        "steps": [
            {
                "step_number": 1,
                "action": "Check string currents across all combiner box channels using a DC clamp meter to identify zero-current strings.",
                "required_tools": ["DC current clamp meter", "Safety goggles"],
                "safety_note": "Maintain 3-point contact on combiner box stands.",
            },
            {
                "step_number": 2,
                "action": "Test combiner box fuse continuity across the dead string with a high-voltage continuity meter.",
                "required_tools": ["1000V DC rated digital multimeter"],
                "safety_note": "Wear insulated gloves rated to 1000V.",
            },
            {
                "step_number": 3,
                "action": "If fuse is blown, inspect string polarity and check for reverse-current or module bypass diode short-circuit.",
                "required_tools": ["Diode test meter", "Infrared thermometer"],
                "safety_note": "Do not insert replacement fuse until short-circuit cause is resolved.",
            },
            {
                "step_number": 4,
                "action": "Replace with authentic gPV fast-acting fuse and confirm restored string amperage.",
                "required_tools": ["Replacement 15A/20A 1000V/1500V gPV fuse", "Fuse puller"],
                "safety_note": "Torque fuse terminals to manufacturer specification.",
            },
        ],
    },
    "ARC_FAULT_AFCI": {
        "title": "DC Arc Fault Detected (AFCI)",
        "category": "ARC_FAULT_AFCI",
        "urgency": "CRITICAL",
        "description": "High-frequency electrical noise characteristic of series or parallel electric arcing detected on the DC bus. Inverter has tripped to prevent electrical fire.",
        "common_codes": ["F063", "E004", "AFCI_FAULT", "ARC_DETECTED", "DC_ARC"],
        "safety_warning": "DANGER: HIGH FIRE RISK. Do not clear AFCI fault remotely without visual physical inspection of array connectors and combiner boxes.",
        "preventative_advice": "Ban cross-mating different MC4 manufacturer brands; use calibrated torque tools on all DC terminations.",
        "steps": [
            {
                "step_number": 1,
                "action": "Perform immediate visual and thermal inspection of all DC combiner boxes, disconnect switches, and module jumper leads.",
                "required_tools": ["Thermal imaging camera", "Class 0 electrical PPE"],
                "safety_note": "Look for charred insulation, melted plastic, or ozone odor.",
            },
            {
                "step_number": 2,
                "action": "Inspect string connector crimps with pull-test check and verify no loose screw terminals on combiner busbars.",
                "required_tools": ["Calibrated torque screwdriver", "Connector extraction tool"],
                "safety_note": "De-energize DC combiner prior to touching terminal screws.",
            },
            {
                "step_number": 3,
                "action": "Replace damaged connectors with matching manufacturer pair and verify tight crimp compression.",
                "required_tools": ["MC4 ratcheting crimper", "Wire stripper"],
                "safety_note": "Ensure proper weather sealing grommet insertion.",
            },
            {
                "step_number": 4,
                "action": "Reset AFCI lock out on inverter control board and observe spectrum analyzer / arc detector during re-energization.",
                "required_tools": ["Inverter diagnostic tool"],
                "safety_note": "Keep personnel clear of array while reconnecting load.",
            },
        ],
    },
    "GRID_CURTAILMENT_OVERVOLTAGE": {
        "title": "Grid Overvoltage Derating / Substation Curtailment",
        "category": "GRID_CURTAILMENT_OVERVOLTAGE",
        "urgency": "MEDIUM",
        "description": "AC grid voltage at point of common coupling (PCC) exceeded statutory ceiling (IEEE 1547 / EN 50549 limit), forcing reactive power injection or inverter curtailment.",
        "common_codes": ["F021", "E005", "GRID_OV", "VOLT_VAR_CURTAIL", "OVERVOLTAGE_AC", "GRID_TRIP"],
        "safety_warning": "NOTICE: Grid-side condition. Verify local distribution tap changer settings before adjusting inverter protective parameters.",
        "preventative_advice": "Enable Volt-VAr and Volt-Watt droop curves (Q(U) and P(U)) to stabilize feeder voltage without complete trip.",
        "steps": [
            {
                "step_number": 1,
                "action": "Measure 3-phase AC voltage and frequency at inverter AC terminals and medium voltage transformer secondary.",
                "required_tools": ["True-RMS power quality analyzer"],
                "safety_note": "Wear arc flash protective gear during live AC measurement.",
            },
            {
                "step_number": 2,
                "action": "Review inverter active power vs reactive power log to verify autonomous Volt-VAr curve response.",
                "required_tools": ["SCADA telemetry logger"],
                "safety_note": "Verify compliance with utility interconnection agreement.",
            },
            {
                "step_number": 3,
                "action": "Coordinate with grid distribution operator (DSO/TSO) to adjust MV transformer off-circuit tap changer (OCTC) by -2.5%.",
                "required_tools": ["Substation key", "Tap changer operating handle"],
                "safety_note": "Transformer must be completely de-energized before tap changing.",
            },
        ],
    },
    "SOILING_DEGRADATION": {
        "title": "Array Soiling / Particulate Contamination Deficit",
        "category": "SOILING_DEGRADATION",
        "urgency": "MEDIUM",
        "description": "Cumulative particulate, dust, bird droppings, or pollen deposition on module glass causing optical transmission attenuation without electrical hardware failure.",
        "common_codes": ["SOILING_DEFICIT", "SOIL_LOSS", "DIRT_DERATE"],
        "safety_warning": "NOTICE: Avoid dry scrubbing dry glass under high midday sun to prevent abrasive micro-scratches and thermal shock.",
        "preventative_advice": "Deploy automated robotic cleaning or schedule semi-monthly washes aligned with rain forecasts.",
        "steps": [
            {
                "step_number": 1,
                "action": "Inspect reference soiling sensor / clean panel witness pair to measure transmission loss ratio.",
                "required_tools": ["Optical soiling station meter", "Pyranometer clean cloth"],
                "safety_note": "Do not step on module glass.",
            },
            {
                "step_number": 2,
                "action": "Evaluate economic break-even point: compare cleaning cost ($/kW) against cumulative generation revenue gain.",
                "required_tools": ["SolarPulse AI yield valuation module"],
                "safety_note": "Schedule cleaning during low-irradiance evening or early morning.",
            },
            {
                "step_number": 3,
                "action": "Execute soft-bristle demineralized water wash or automated dry tractor brush across the affected sub-array.",
                "required_tools": ["Water filtration rig (<50 ppm TDS)", "Rotary brush trolley"],
                "safety_note": "Water pressure must remain under 35 psi to protect anti-reflective module coating.",
            },
        ],
    },
    "INVERTER_CLIPPING_SATURATION": {
        "title": "Inverter DC-to-AC Ratio Clipping (Expected Physical Ceiling)",
        "category": "INVERTER_CLIPPING_SATURATION",
        "urgency": "LOW",
        "description": "DC power generated by panels exceeds inverter AC rated export capacity during high irradiance; normal operational power limiting.",
        "common_codes": ["CLIPPING", "AC_LIMIT", "POWER_CAP"],
        "safety_warning": "INFORMATIONAL: Expected system design behavior. No equipment fault present.",
        "preventative_advice": "Consider co-located BESS charging to capture clipped DC energy before inverter conversion.",
        "steps": [
            {
                "step_number": 1,
                "action": "Verify that inverter export power matches plant inverter_capacity_kw rating.",
                "required_tools": ["SCADA telemetry check"],
                "safety_note": "No field intervention required.",
            },
            {
                "step_number": 2,
                "action": "Assess BESS DC-coupled charging capture potential during peak clipping hours.",
                "required_tools": ["SolarPulse AI battery optimizer"],
                "safety_note": "Ensure battery SOC allows daytime charge absorption.",
            },
        ],
    },
    "MPPT_TRACKER_FAILURE": {
        "title": "Single-Axis Tracker Mechanical Stalling / MPPT Sub-Array Error",
        "category": "MPPT_TRACKER_FAILURE",
        "urgency": "HIGH",
        "description": "Single-axis tracker slew drive stalled or locked at off-sun angle, creating cosine angle incidence losses across the torque tube.",
        "common_codes": ["F077", "E006", "TRACKER_ERR", "SLEW_FAIL", "INCLINOMETER_ALARM"],
        "safety_warning": "CAUTION: Tracker drive gears exert massive mechanical torque. Disengage motor power before inspecting mechanical linkages.",
        "preventative_advice": "Lubricate slew drives semi-annually and inspect emergency wind-stow battery backups.",
        "steps": [
            {
                "step_number": 1,
                "action": "Inspect tracker inclinometer sensor reading against astronomical target sun angle.",
                "required_tools": ["Digital inclinometer", "Tracker TCU interface"],
                "safety_note": "Stay clear of torque tube rotation path.",
            },
            {
                "step_number": 2,
                "action": "Check tracker 24V DC drive motor, mechanical linkages, and bearing mounts for binding or shear pin rupture.",
                "required_tools": ["Socket set", "Replacement shear pins"],
                "safety_note": "Lock out motor breaker before handling mechanical joints.",
            },
            {
                "step_number": 3,
                "action": "Manually jog tracker east/west to confirm free travel and calibrate home position index.",
                "required_tools": ["Manual jog handset"],
                "safety_note": "Verify wind speed is below 15 m/s before manually tilting array.",
            },
        ],
    },
    "COMMUNICATION_SCADA_LOSS": {
        "title": "SCADA Gateway / Sensor Telemetry Drop (Phantom Shortfall)",
        "category": "COMMUNICATION_SCADA_LOSS",
        "urgency": "LOW",
        "description": "Inverter or pyranometer reporting stale or zero data due to Ethernet/RS485 bus packet loss, while actual AC generation remains intact.",
        "common_codes": ["F088", "E007", "COMM_TIMEOUT", "MODBUS_ERR", "OFFLINE"],
        "safety_warning": "NOTICE: Verify utility revenue meter generation before deploying field technicians for inverter replacement.",
        "preventative_advice": "Verify RS485 termination resistors (120 Ohm) and surge arrestors on communication lines.",
        "steps": [
            {
                "step_number": 1,
                "action": "Check revenue meter / grid export logger to confirm actual high-voltage generation is flowing.",
                "required_tools": ["Revenue meter web portal"],
                "safety_note": "No electrical hazard.",
            },
            {
                "step_number": 2,
                "action": "Reboot plant communication gateway / Modbus edge logger and inspect fiber-optic switch link lights.",
                "required_tools": ["Gateway console cable", "Ethernet tester"],
                "safety_note": "Ensure configuration backup is saved before power cycling.",
            },
        ],
    },
}


# ── Diagnostic Engine Core ───────────────────────────────────────────────────

def get_root_cause_taxonomy() -> List[RootCauseTaxonomyItem]:
    """Returns all supported root cause diagnostic categories and descriptions."""
    items: List[RootCauseTaxonomyItem] = []
    for cat, data in DIAGNOSTIC_TAXONOMY.items():
        items.append(
            RootCauseTaxonomyItem(
                category=cat,
                title=data["title"],
                common_error_codes=data["common_codes"],
                description=data["description"],
                typical_urgency=data["urgency"],
            )
        )
    return items


def _match_error_code(code_str: str) -> Optional[Tuple[str, float]]:
    """Matches an inverter error code string to a known root cause category."""
    norm = code_str.upper().strip()
    if not norm or len(norm) < 3:
        return None

    for cat, data in DIAGNOSTIC_TAXONOMY.items():
        for c in data["common_codes"]:
            if norm == c or (len(c) >= 4 and c in norm):
                return cat, 96.0  # High confidence on direct code match
    return None


def _evaluate_telemetry_patterns(
    expected_kw: float,
    actual_kw: float,
    irradiance: Optional[float],
    temperature_c: Optional[float],
    module_temp_c: Optional[float],
    days_since_cleaning: Optional[float],
    alert_message: Optional[str],
) -> Tuple[str, float]:
    """
    Evaluates multi-modal telemetry and textual context to identify root cause
    when specific error codes are absent.
    """
    deficit_ratio = (
        (expected_kw - actual_kw) / max(expected_kw, 1.0) if expected_kw > 0 else 0.0
    )
    msg_upper = (alert_message or "").upper()

    # 1. Textual clues in alert message
    if "TRIP" in msg_upper or "DISCONNECT" in msg_upper or "OVERHEAT" in msg_upper:
        if (module_temp_c and module_temp_c > 52.0) or (temperature_c and temperature_c > 36.0):
            return "INVERTER_TRIP_OVERTEMP", 92.0
        return "INVERTER_TRIP_OVERTEMP", 88.0

    if "SOIL" in msg_upper or "DIRT" in msg_upper or "DUST" in msg_upper:
        return "SOILING_DEGRADATION", 94.0

    if "CLIP" in msg_upper or "SATURAT" in msg_upper:
        return "INVERTER_CLIPPING_SATURATION", 97.0

    if "CURTAIL" in msg_upper or "GRID" in msg_upper or "OVERVOLT" in msg_upper:
        return "GRID_CURTAILMENT_OVERVOLTAGE", 93.0

    if "GROUND" in msg_upper or "INSULAT" in msg_upper or "RISO" in msg_upper:
        return "GROUND_FAULT_INSULATION", 95.0

    if "ARC" in msg_upper or "AFCI" in msg_upper:
        return "ARC_FAULT_AFCI", 96.0

    # 2. Physics & telemetry signature heuristics
    irr = irradiance if irradiance is not None else 650.0

    # Steep drop under high sun (> 25% drop)
    if deficit_ratio >= 0.25 and irr > 400.0:
        if (module_temp_c and module_temp_c > 50.0) or (temperature_c and temperature_c > 35.0):
            return "INVERTER_TRIP_OVERTEMP", 89.0
        elif deficit_ratio < 0.60:
            # Typical fractional string / combiner loss
            return "DC_STRING_FAULT", 84.0
        else:
            # Complete inverter shutdown
            return "INVERTER_TRIP_OVERTEMP", 82.0

    # Moderate deficit (8% - 24%) under high sun -> soiling or tracker
    if 0.08 <= deficit_ratio < 0.25:
        if days_since_cleaning and days_since_cleaning >= 10.0:
            return "SOILING_DEGRADATION", 89.0
        return "SOILING_DEGRADATION", 78.0

    # Minimal deficit with actual matching expected -> Clipping or normal
    if deficit_ratio < 0.08:
        if irr > 750.0:
            return "INVERTER_CLIPPING_SATURATION", 85.0
        return "COMMUNICATION_SCADA_LOSS", 72.0

    # Fallback default
    return "DC_STRING_FAULT", 70.0


def diagnose_root_cause(
    plant_id: int,
    plant_name: Optional[str] = "Solar Plant",
    capacity_kw: float = 1000.0,
    alert_id: Optional[int] = None,
    alert_message: Optional[str] = None,
    inverter_error_code: Optional[str] = None,
    expected_power_kw: Optional[float] = None,
    actual_power_kw: Optional[float] = None,
    irradiance_w_m2: Optional[float] = None,
    temperature_c: Optional[float] = None,
    module_temp_c: Optional[float] = None,
    days_since_cleaning: Optional[float] = None,
    notes: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> DiagnosisResponse:
    """
    Performs AI-driven root-cause diagnosis using error codes, electrical telemetry,
    and environmental conditions.
    """
    ts = timestamp or datetime.now(tz=timezone.utc)
    exp_kw = expected_power_kw if expected_power_kw is not None else capacity_kw * 0.75
    act_kw = actual_power_kw if actual_power_kw is not None else exp_kw * 0.65

    loss_kw = max(0.0, exp_kw - act_kw)
    daily_revenue_loss = round(loss_kw * DEFAULT_PEAK_SUN_HOURS * DEFAULT_PPA_TARIFF_PER_KWH, 2)

    category: str
    confidence: float

    # Phase 1: Inverter error code matching
    matched_code = None
    if inverter_error_code:
        code_match = _match_error_code(inverter_error_code)
        if code_match:
            category, confidence = code_match
            matched_code = inverter_error_code

    # Phase 2: If code not provided or unmatched, evaluate telemetry patterns
    if not inverter_error_code or not matched_code:
        # Also check if alert_message contains a specific error code token (e.g. F056 or F034)
        if alert_message:
            import re
            tokens = re.findall(r'\b[FEW]\d{3,4}\b|\bAFCI\b|\bRISO\b|\bISO[-_]?FAULT\b', alert_message.upper())
            for tok in tokens:
                m = _match_error_code(tok)
                if m:
                    category, confidence = m
                    matched_code = tok
                    break

        if not matched_code:
            category, confidence = _evaluate_telemetry_patterns(
                expected_kw=exp_kw,
                actual_kw=act_kw,
                irradiance=irradiance_w_m2,
                temperature_c=temperature_c,
                module_temp_c=module_temp_c,
                days_since_cleaning=days_since_cleaning,
                alert_message=alert_message or notes,
            )

    tax_entry = DIAGNOSTIC_TAXONOMY.get(
        category, DIAGNOSTIC_TAXONOMY["DC_STRING_FAULT"]
    )

    steps = [
        TechnicianStep(
            step_number=s["step_number"],
            action=s["action"],
            required_tools=s.get("required_tools", []),
            safety_note=s.get("safety_note"),
        )
        for s in tax_entry["steps"]
    ]

    telemetry_evidence = {
        "expected_power_kw": round(exp_kw, 2),
        "actual_power_kw": round(act_kw, 2),
        "power_shortfall_kw": round(loss_kw, 2),
        "deficit_percentage": round(((exp_kw - act_kw) / max(exp_kw, 1.0)) * 100.0, 1),
        "irradiance_w_m2": round(irradiance_w_m2, 1) if irradiance_w_m2 is not None else None,
        "temperature_c": round(temperature_c, 1) if temperature_c is not None else None,
        "module_temp_c": round(module_temp_c, 1) if module_temp_c is not None else None,
        "detected_error_code": matched_code or inverter_error_code,
    }

    summary = (
        f"AI Diagnosis identified {tax_entry['title']} with {confidence:.0f}% confidence. "
        f"Estimated power deficit of {loss_kw:.1f} kW represents ${daily_revenue_loss:.2f}/day revenue impact."
    )

    return DiagnosisResponse(
        id=None,
        plant_id=plant_id,
        plant_name=plant_name,
        alert_id=alert_id,
        timestamp=ts,
        root_cause_category=category,
        root_cause_title=tax_entry["title"],
        confidence_score=round(confidence, 1),
        inverter_error_code=matched_code or inverter_error_code,
        estimated_loss_kw=round(loss_kw, 2),
        financial_impact_per_day=daily_revenue_loss,
        urgency_level=tax_entry["urgency"],
        summary=summary,
        root_cause_details=tax_entry["description"],
        technician_steps=steps,
        safety_warning=tax_entry.get("safety_warning"),
        preventative_advice=tax_entry.get("preventative_advice"),
        telemetry_evidence=telemetry_evidence,
        created_at=datetime.now(tz=timezone.utc),
    )


# ── Database Persistence Helpers ─────────────────────────────────────────────

async def persist_diagnosis(
    db: AsyncSession,
    diag: DiagnosisResponse,
) -> DiagnosisRecord:
    """Persists a DiagnosisResponse into the diagnosis_records database table."""
    steps_json = json.dumps([s.model_dump() for s in diag.technician_steps])

    record = DiagnosisRecord(
        plant_id=diag.plant_id,
        alert_id=diag.alert_id,
        timestamp=diag.timestamp,
        root_cause_category=diag.root_cause_category,
        root_cause_title=diag.root_cause_title,
        confidence_score=diag.confidence_score,
        inverter_error_code=diag.inverter_error_code,
        estimated_loss_kw=diag.estimated_loss_kw,
        financial_impact_per_day=diag.financial_impact_per_day,
        urgency_level=diag.urgency_level,
        summary=diag.summary,
        root_cause_details=diag.root_cause_details,
        technician_steps_json=steps_json,
        safety_warning=diag.safety_warning,
        preventative_advice=diag.preventative_advice,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_diagnosis_by_alert_id(
    db: AsyncSession,
    alert_id: int,
) -> Optional[DiagnosisResponse]:
    """Retrieves existing diagnosis for an alert if already computed."""
    result = await db.execute(
        select(DiagnosisRecord)
        .where(DiagnosisRecord.alert_id == alert_id)
        .order_by(DiagnosisRecord.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if not record:
        return None

    steps = [
        TechnicianStep(**s) for s in json.loads(record.technician_steps_json)
    ]
    return DiagnosisResponse(
        id=record.id,
        plant_id=record.plant_id,
        alert_id=record.alert_id,
        timestamp=record.timestamp,
        root_cause_category=record.root_cause_category,
        root_cause_title=record.root_cause_title,
        confidence_score=record.confidence_score,
        inverter_error_code=record.inverter_error_code,
        estimated_loss_kw=record.estimated_loss_kw,
        financial_impact_per_day=record.financial_impact_per_day,
        urgency_level=record.urgency_level,
        summary=record.summary,
        root_cause_details=record.root_cause_details,
        technician_steps=steps,
        safety_warning=record.safety_warning,
        preventative_advice=record.preventative_advice,
        created_at=record.created_at,
    )


async def run_diagnosis_for_alert(
    db: AsyncSession,
    alert_id: int,
) -> DiagnosisResponse:
    """
    Looks up an AnomalyAlert, queries plant metadata and SCADA telemetry,
    executes AI root cause diagnosis, persists the result, and returns the response.
    """
    alert_res = await db.execute(select(AnomalyAlert).where(AnomalyAlert.id == alert_id))
    alert: Optional[AnomalyAlert] = alert_res.scalar_one_or_none()
    if not alert:
        raise ValueError(f"AnomalyAlert with ID {alert_id} not found.")

    # Check if already diagnosed
    existing = await get_diagnosis_by_alert_id(db, alert_id)
    if existing:
        return existing

    # Look up Plant
    plant_res = await db.execute(select(Plant).where(Plant.id == alert.plant_id))
    plant: Optional[Plant] = plant_res.scalar_one_or_none()
    plant_name = plant.name if plant else f"Plant #{alert.plant_id}"
    capacity_kw = plant.capacity_kw if plant else 1000.0

    # Look up SCADA telemetry at that timestamp or recent
    scada_res = await db.execute(
        select(ScadaReading)
        .where(ScadaReading.plant_id == alert.plant_id)
        .where(ScadaReading.timestamp <= alert.timestamp)
        .order_by(ScadaReading.timestamp.desc())
        .limit(1)
    )
    latest_scada: Optional[ScadaReading] = scada_res.scalar_one_or_none()

    irradiance = latest_scada.irradiance_w_m2 if latest_scada else 750.0
    temp = latest_scada.temperature_c if latest_scada else 32.0
    mod_temp = latest_scada.module_temperature_c if latest_scada else 48.0

    diagnosis = diagnose_root_cause(
        plant_id=alert.plant_id,
        plant_name=plant_name,
        capacity_kw=capacity_kw,
        alert_id=alert.id,
        alert_message=alert.message,
        expected_power_kw=alert.expected_power_kw,
        actual_power_kw=alert.actual_power_kw,
        irradiance_w_m2=irradiance,
        temperature_c=temp,
        module_temp_c=mod_temp,
        timestamp=alert.timestamp,
    )

    saved = await persist_diagnosis(db, diagnosis)
    diagnosis.id = saved.id
    return diagnosis


async def list_diagnoses_by_plant(
    db: AsyncSession,
    plant_id: int,
    limit: int = 50,
) -> List[DiagnosisResponse]:
    """Retrieves all diagnosed records for a plant."""
    result = await db.execute(
        select(DiagnosisRecord)
        .where(DiagnosisRecord.plant_id == plant_id)
        .order_by(DiagnosisRecord.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()

    responses: List[DiagnosisResponse] = []
    for r in records:
        steps = [TechnicianStep(**s) for s in json.loads(r.technician_steps_json)]
        responses.append(
            DiagnosisResponse(
                id=r.id,
                plant_id=r.plant_id,
                alert_id=r.alert_id,
                timestamp=r.timestamp,
                root_cause_category=r.root_cause_category,
                root_cause_title=r.root_cause_title,
                confidence_score=r.confidence_score,
                inverter_error_code=r.inverter_error_code,
                estimated_loss_kw=r.estimated_loss_kw,
                financial_impact_per_day=r.financial_impact_per_day,
                urgency_level=r.urgency_level,
                summary=r.summary,
                root_cause_details=r.root_cause_details,
                technician_steps=steps,
                safety_warning=r.safety_warning,
                preventative_advice=r.preventative_advice,
                created_at=r.created_at,
            )
        )
    return responses
