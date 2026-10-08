"""
Model training CLI pipeline for SolarPulse AI.
Orchestrates data preparation, feature extraction, cross-validation,
hyperparameter optimization, evaluation, and artifact versioning.
Operates on CPU (no GPU required).
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# Ensure repository root is in sys.path when executed directly
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from backend.ml.config import PlantConfig
from backend.ml.features.feature_pipeline import SolarFeaturePipeline
from backend.ml.models.lightgbm_model import LightGBMForecaster, HAS_LIGHTGBM
from backend.ml.training.cross_validate import PurgedTimeSeriesSplit
from backend.ml.training.evaluate import evaluate_forecast
from backend.ml.training.hyperparams import run_hyperparameter_optimization, HAS_OPTUNA

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("solarpulse.train")


def generate_synthetic_training_data(
    start_date: str = "2024-01-01",
    end_date: str = "2024-03-31",
    freq: str = "1h",
    capacity_dc_kw: float = 1000.0
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Generates synthetic realistic weather and SCADA power data for testing the pipeline
    without external database access.
    """
    times = pd.date_range(start=start_date, end=end_date, freq=freq, tz="UTC")
    n = len(times)

    # Synthetic diurnal solar cycle
    hours = times.hour.values + times.minute.values / 60.0
    daylight = (hours >= 6) & (hours <= 18)
    solar_shape = np.maximum(0.0, np.sin(np.pi * (hours - 6) / 12.0)) ** 1.3
    solar_shape[~daylight] = 0.0

    # Solar irradiance
    ghi = 1000.0 * solar_shape * (0.8 + 0.2 * np.random.uniform(0.7, 1.0, n))
    dni = np.where(ghi > 50, ghi * 1.15, 0.0)
    dhi = np.where(ghi > 50, ghi * 0.25, 0.0)
    cloud_cover = np.random.uniform(0.0, 60.0, n)
    temp = 20.0 + 10.0 * solar_shape + np.random.normal(0, 2.0, n)
    wind = np.random.uniform(0.5, 5.0, n)

    weather_df = pd.DataFrame({
        "ghi_nwp": ghi,
        "dni_nwp": dni,
        "dhi_nwp": dhi,
        "temp_ambient_nwp": temp,
        "wind_speed_nwp": wind,
        "cloud_cover_pct": cloud_cover,
    }, index=times)

    # Target: Gross DC power (kW)
    # Simple physical approximation: efficiency factor ~0.18, derates ~0.85
    gross_dc_power = (ghi / 1000.0) * capacity_dc_kw * 0.9 + np.random.normal(0, 10.0, n)
    gross_dc_power = np.clip(gross_dc_power, 0.0, capacity_dc_kw)
    gross_dc_power[~daylight] = 0.0
    target_series = pd.Series(gross_dc_power, index=times, name="gross_dc_power_kw")

    return weather_df, target_series


def train_pipeline(
    plant_config: PlantConfig,
    weather_df: pd.DataFrame,
    target: pd.Series,
    output_dir: Path,
    version: str = "1.0.0",
    tune_hyperparams: bool = False,
    n_splits: int = 5,
    purge_gap_steps: int = 24
) -> Path:
    """
    Full ML training workflow execution.
    """
    logger.info("Starting SolarPulse training pipeline for plant: %s", plant_config.plant_id)
    logger.info("Target dataset samples: %d", len(weather_df))

    # 1. Feature Engineering via SolarFeaturePipeline
    logger.info("Computing pvlib physics and meteorological features...")
    pipeline = SolarFeaturePipeline(plant_config=plant_config)
    X = pipeline.transform(weather_df)
    y = target.values

    # 2. Chronological Train / Test Split (Holdout test = last 15%)
    split_idx = int(len(X) * 0.85)
    X_train_full, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train_full, y_test = y[:split_idx], y[split_idx:]

    logger.info("Split dataset: Train=%d samples, Held-out Test=%d samples", len(X_train_full), len(X_test))

    # 3. Hyperparameter Tuning (Optional)
    best_params = None
    if tune_hyperparams:
        if HAS_OPTUNA:
            logger.info("Running Optuna hyperparameter optimization...")
            best_params = run_hyperparameter_optimization(X_train_full, y_train_full, n_trials=30)
            logger.info("Optimal hyperparameters: %s", best_params)
        else:
            logger.warning("Optuna not installed; skipping hyperparameter tuning.")

    # 4. Cross-Validation on Training Set
    logger.info("Running purged walk-forward cross-validation (%d folds, gap=%d)...", n_splits, purge_gap_steps)
    cv = PurgedTimeSeriesSplit(n_splits=n_splits, purge_gap_steps=purge_gap_steps)
    fold_reports = []

    for fold_num, (tr_idx, val_idx) in enumerate(cv.split(X_train_full, y_train_full), 1):
        X_tr, y_tr = X_train_full.iloc[tr_idx], y_train_full[tr_idx]
        X_va, y_va = X_train_full.iloc[val_idx], y_train_full[val_idx]

        fold_model = LightGBMForecaster(params=best_params)
        fold_model.fit(X_tr, y_tr, X_val=X_va, y_val=y_va, early_stopping_rounds=20)
        preds_va = fold_model.predict(X_va)
        report = evaluate_forecast(y_va, preds_va, capacity_kw=plant_config.capacity_dc_kw)
        fold_reports.append(report)
        logger.info("Fold %d - RMSE: %.2f kW, MAPE: %.2f%%", fold_num, report["rmse_kw"], report["mape_pct"])

    # 5. Final Model Fit on Full Training Set with held-out validation
    logger.info("Refitting final forecaster on full training set...")
    final_model = LightGBMForecaster(params=best_params, version=version)
    final_model.fit(X_train_full, y_train_full, X_val=X_test, y_val=y_test, early_stopping_rounds=30)

    # 6. Evaluation on Held-Out Test Set
    test_preds = final_model.predict(X_test)
    test_report = evaluate_forecast(y_test, test_preds, capacity_kw=plant_config.capacity_dc_kw)
    logger.info("=== HELD-OUT TEST EVALUATION ===")
    logger.info("RMSE: %.2f kW | MAE: %.2f kW | MAPE: %.2f%% | R2: %.4f | MBE: %.2f kW",
                test_report["rmse_kw"], test_report["mae_kw"], test_report["mape_pct"],
                test_report["r2_score"], test_report["mbe_kw"])

    # 7. Model Serialization
    output_dir.mkdir(parents=True, exist_ok=True)
    versioned_filename = f"lgbm_{plant_config.plant_id}_v{version}.pkl"
    artifact_path = output_dir / versioned_filename
    final_model.metadata["cv_reports"] = fold_reports
    final_model.metadata["test_report"] = test_report
    final_model.metadata["trained_at"] = datetime.now(timezone.utc).isoformat()
    final_model.save(artifact_path)
    logger.info("Serialized model artifact saved to: %s", artifact_path)

    # Save metrics report JSON
    metrics_path = output_dir / f"metrics_{plant_config.plant_id}_v{version}.json"
    with open(metrics_path, "w") as f:
        json.dump(test_report, f, indent=2)

    # 8. Update 'lgbm_latest.pkl'
    latest_path = output_dir / "lgbm_latest.pkl"
    try:
        if latest_path.is_symlink() or latest_path.exists():
            latest_path.unlink()
        shutil.copy2(artifact_path, latest_path)
        logger.info("Updated latest model pointer: %s", latest_path)
    except Exception as e:
        logger.warning("Could not create alias link/copy: %s", e)

    return artifact_path


def parse_args():
    parser = argparse.ArgumentParser(description="SolarPulse AI Model Training Pipeline")
    parser.add_argument("--plant-id", type=str, default="P01", help="Plant identifier")
    parser.add_argument("--start", type=str, default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default="2024-03-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--version", type=str, default="1.0.0", help="Model version tag")
    parser.add_argument("--tune", action="store_true", help="Enable Optuna hyperparameter search")
    parser.add_argument("--data-path", type=str, default=None, help="Path to input dataset CSV/parquet")
    parser.add_argument("--output-dir", type=str, default=None, help="Artifact output directory")
    parser.add_argument("--dry-run", action="store_true", help="Run quick synthetic test without external data")
    return parser.parse_args()


def main():
    args = parse_args()

    default_output_dir = Path(__file__).resolve().parent.parent / "artifacts" / "models"
    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir

    plant_config = PlantConfig(
        plant_id=args.plant_id,
        name=f"Plant {args.plant_id}",
        latitude=28.6139,
        longitude=77.2090,
        tilt_deg=25.0,
        azimuth_deg=180.0,
        capacity_dc_kw=1000.0,
        ac_export_limit_kw=850.0,
    )

    if args.dry_run or args.data_path is None:
        logger.info("Executing synthetic smoke test pipeline...")
        weather_df, target = generate_synthetic_training_data(
            start_date=args.start,
            end_date=args.end,
            capacity_dc_kw=plant_config.capacity_dc_kw
        )
    else:
        logger.info("Loading training dataset from: %s", args.data_path)
        data = pd.read_parquet(args.data_path) if args.data_path.endswith(".parquet") else pd.read_csv(args.data_path, parse_dates=["time"], index_col="time")
        target = data["gross_dc_power_kw"]
        weather_df = data.drop(columns=["gross_dc_power_kw"], errors="ignore")

    train_pipeline(
        plant_config=plant_config,
        weather_df=weather_df,
        target=target,
        output_dir=output_dir,
        version=args.version,
        tune_hyperparams=args.tune
    )


if __name__ == "__main__":
    main()
