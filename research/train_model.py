"""
WP5 — Train ML Model v2 (Offline, Shadow Mode)

Trains a classifier on labeled scan results to predict whether a setup
will be profitable. Runs in shadow mode first — does NOT affect entries
until promoted by the WP6 promotion gate.

Usage:
    python research/train_model.py --dry-run
    python research/train_model.py --train --min-signals 300

Flags:
    --dry-run       Print dataset stats, don't train
    --train         Train and save model to database
    --min-signals   Minimum labeled signals required (default 300)
    --notional      Notional position size for r_net calc (default 25000)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score, brier_score_loss, classification_report,
    confusion_matrix, roc_auc_score
)
from sklearn.model_selection import TimeSeriesSplit

sys.path.insert(0, '.')
from core.features import FEATURE_NAMES, NUM_FEATURES, build_features
from models.database import get_session, MLModel, SignalLabel
from models.scan_report import ScanResult, ScanReport

logger = logging.getLogger(__name__)

DEFAULT_MIN_SIGNALS = 300


def load_labeled_data(session, min_signals: int = DEFAULT_MIN_SIGNALS) -> pd.DataFrame:
    """
    Load labeled signals with features from the database.

    Joins signal_labels with scan_results to get features_json and market context.
    Only includes rows where features_json is not null and r_net is not null.
    """
    from sqlalchemy import func

    query = (
        session.query(
            SignalLabel,
            ScanResult.features_json,
            ScanReport.market_trend,
            ScanReport.market_strength,
        )
        .join(ScanResult, SignalLabel.scan_result_id == ScanResult.id)
        .join(ScanReport, ScanResult.scan_report_id == ScanReport.id)
        .filter(SignalLabel.r_net.isnot(None))
        .filter(ScanResult.features_json.isnot(None))
    )

    rows = query.all()
    records = []

    for sl, features_json, trend, strength in rows:
        try:
            features_list = json.loads(features_json) if features_json else []
            if not features_list or len(features_list) != NUM_FEATURES:
                continue
            features = dict(zip(FEATURE_NAMES, features_list))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

        record = dict(features)
        record['r_net'] = sl.r_net
        record['outcome'] = sl.outcome
        record['scan_result_id'] = sl.scan_result_id
        record['symbol'] = sl.symbol
        record['signal_date'] = sl.signal_date
        record['market_trend'] = trend
        record['market_strength'] = strength
        records.append(record)

    df = pd.DataFrame(records)
    logger.info(f"Loaded {len(df)} labeled signals with features")

    if len(df) < min_signals:
        logger.error(
            f"Insufficient labeled signals: {len(df)} < {min_signals} minimum. "
            f"Run label_outcomes.py first."
        )
        return pd.DataFrame()

    return df


def prepare_xy(df: pd.DataFrame):
    """
    Split dataframe into X (features) and y (binary target: r_net > 0).

    Target = 1 if the trade made net profit (r_net > 0), 0 otherwise.
    """
    feature_cols = [f for f in FEATURE_NAMES if f in df.columns]
    missing = [f for f in FEATURE_NAMES if f not in df.columns]
    if missing:
        logger.warning(f"Missing features: {missing}")

    X = df[feature_cols].astype(float).values
    y = (df['r_net'] > 0).astype(int).values

    return X, y


def train_model(X: np.ndarray, y: np.ndarray):
    """
    Train HistGradientBoostingClassifier with purged time-series CV.

    Returns trained model and validation metrics.
    """
    n_samples = len(X)
    n_splits = min(5, max(2, n_samples // 50))

    # Purged time-series split — no shuffle, respect temporal order
    tscv = TimeSeriesSplit(n_splits=n_splits)

    fold_aucs = []
    fold_briers = []
    fold_predictions = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        if len(np.unique(y_train)) < 2:
            logger.warning(f"Fold {fold}: only one class in train, skipping")
            continue

        model = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_depth=6,
            min_samples_leaf=max(5, n_samples // 200),
            random_state=42,
        )
        model.fit(X_train, y_train)

        y_pred_proba = model.predict_proba(X_val)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)

        auc = roc_auc_score(y_val, y_pred_proba) if len(np.unique(y_val)) > 1 else 0.5
        brier = brier_score_loss(y_val, y_pred_proba)
        acc = accuracy_score(y_val, y_pred)

        fold_aucs.append(auc)
        fold_briers.append(brier)
        fold_predictions.extend(list(zip(y_val, y_pred_proba)))

        logger.info(
            f"Fold {fold + 1}: train={len(train_idx)}, val={len(val_idx)}, "
            f"AUC={auc:.3f}, Brier={brier:.3f}, Acc={acc:.3f}"
        )

    # Train final model on all data
    final_model = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.05,
        max_depth=6,
        min_samples_leaf=max(5, n_samples // 200),
        random_state=42,
    )
    final_model.fit(X, y)

    # Calibrate using the full dataset (isotonic)
    try:
        calibrated = CalibratedClassifierCV(final_model, method='isotonic', cv=5)
        calibrated.fit(X, y)
    except Exception:
        # Fallback: use uncalibrated model if calibration fails
        logger.warning("Calibration failed, using uncalibrated model")
        calibrated = final_model

    metrics = {
        'n_samples': n_samples,
        'n_folds': n_splits,
        'mean_auc': float(np.mean(fold_aucs)) if fold_aucs else 0.0,
        'mean_brier': float(np.mean(fold_briers)) if fold_briers else 0.0,
        'mean_accuracy': float(np.mean([p[0] == round(p[1]) for p in fold_predictions])) if fold_predictions else 0.0,
        'feature_names': FEATURE_NAMES,
        'n_features': NUM_FEATURES,
        'trained_at': datetime.now().isoformat(),
    }
    # Get feature importances if available
    if hasattr(final_model, 'feature_importances_'):
        feature_importances = {}
        for name, imp in zip(FEATURE_NAMES, final_model.feature_importances_.tolist()):
            feature_importances[name] = float(imp)
        metrics['feature_importances'] = feature_importances
        logger.info(f"Top features:")
        for name, imp in sorted(
            feature_importances.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]:
            logger.info(f"  {name}: {imp:.4f}")
    else:
        logger.info("Feature importances not available for this model type")

    return calibrated, metrics


def save_model(model, metrics: dict, session):
    """
    Save trained model to database as pattern_classifier_v2 with is_active=False.
    """
    import pickle
    import io

    model_bytes = io.BytesIO()
    joblib.dump(model, model_bytes)
    model_bytes.seek(0)

    metadata = {
        **metrics,
        'model_type': 'HistGradientBoostingClassifier + IsotonicCalibration',
        'target': 'r_net > 0',
        'note': 'Shadow mode only — does not affect entries until promoted',
    }

    # Deactivate any existing v2 model
    existing = (
        session.query(MLModel)
        .filter_by(model_name='pattern_classifier_v2')
        .all()
    )
    for m in existing:
        m.is_active = False

    model_record = MLModel(
        model_name='pattern_classifier_v2',
        model_data=model_bytes.getvalue(),
        scaler_data=b'',  # Not used — features are already scaled/normalized
        is_active=False,  # Shadow mode only
        created_at=datetime.now(),
        accuracy=metrics.get('mean_auc', 0.0),
    )
    session.add(model_record)
    session.commit()
    session.refresh(model_record)

    logger.info(f"Saved model pattern_classifier_v2 (id={model_record.id}, is_active=False)")
    return model_record.id


def main():
    parser = argparse.ArgumentParser(description='WP5 — Train ML Model v2 (offline, shadow mode)')
    parser.add_argument('--dry-run', action='store_true', help='Print dataset stats, don’t train')
    parser.add_argument('--train', action='store_true', help='Train and save model to database')
    parser.add_argument('--min-signals', type=int, default=DEFAULT_MIN_SIGNALS,
                        help='Minimum labeled signals required (default 300)')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    with get_session() as session:
        df = load_labeled_data(session, min_signals=args.min_signals)

        if df.empty:
            logger.warning("No data available for training")
            return

        if args.dry_run:
            logger.info(f"DRY RUN: {len(df)} labeled signals available for training")
            logger.info(f"Target distribution (r_net > 0): {(df['r_net'] > 0).mean():.1%}")
            logger.info(f"Feature columns: {len(FEATURE_NAMES)}")
            return

        X, y = prepare_xy(df)
        logger.info(f"Training on {len(X)} samples, {X.shape[1]} features")
        logger.info(f"Target positive rate: {y.mean():.1%}")

        model, metrics = train_model(X, y)

        logger.info("\n=== Training Complete ===")
        logger.info(f"Mean AUC: {metrics['mean_auc']:.3f}")
        logger.info(f"Mean Brier: {metrics['mean_brier']:.3f}")
        logger.info(f"Mean Accuracy: {metrics['mean_accuracy']:.3f}")
        logger.info(f"Top features:")
        if 'feature_importances' in metrics:
            for name, imp in sorted(
                metrics['feature_importances'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:
                logger.info(f"  {name}: {imp:.4f}")
        else:
            logger.info("Feature importances not available for this model type")

        model_id = save_model(model, metrics, session)
        logger.info(f"\nModel saved as pattern_classifier_v2 (id={model_id}, is_active=False)")
        logger.info("Run in shadow mode — does not affect entries until promoted")


if __name__ == '__main__':
    main()
