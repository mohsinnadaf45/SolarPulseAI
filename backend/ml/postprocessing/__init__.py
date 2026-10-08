"""
Post-processing modules for operational derates: inverter clipping and soiling.
"""

from backend.ml.postprocessing.clipping import (
    apply_clipping,
    calculate_clipping_metrics,
)
from backend.ml.postprocessing.soiling import (
    calculate_dynamic_soiling,
    apply_soiling_loss,
    calculate_soiling_metrics,
)
from backend.ml.postprocessing.ramp_risk import (
    RampDirection,
    RampRiskLevel,
    RampPointMetrics,
    RampRiskSummary,
    classify_ramp_risk,
    calculate_bess_reserve_recommendation,
    compute_ramp_risk_profile,
)

__all__ = [
    "apply_clipping",
    "calculate_clipping_metrics",
    "calculate_dynamic_soiling",
    "apply_soiling_loss",
    "calculate_soiling_metrics",
    "RampDirection",
    "RampRiskLevel",
    "RampPointMetrics",
    "RampRiskSummary",
    "classify_ramp_risk",
    "calculate_bess_reserve_recommendation",
    "compute_ramp_risk_profile",
]
