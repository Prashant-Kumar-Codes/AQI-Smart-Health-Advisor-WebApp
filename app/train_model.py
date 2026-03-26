"""
Improved AQI Model Training - Multi-Horizon Prediction
=======================================================
Trains 12 separate Random Forest models:
- Model 1: Predicts 1 hour ahead
- Model 2: Predicts 2 hours ahead
- ...
- Model 12: Predicts 12 hours ahead

This gives much better hourly predictions compared to iterative forecasting.

Author: AQI Prediction System
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

# Data configuration
DATA_FILE = 'aqi_ml_dataset.csv'  # From preprocessing script

# Model configuration
MODELS_DIR = 'models'
os.makedirs(MODELS_DIR, exist_ok=True)

# Training parameters
TEST_SIZE = 0.2
RANDOM_STATE = 42
N_ESTIMATORS = 200
MAX_DEPTH = 20
MIN_SAMPLES_SPLIT = 5
MIN_SAMPLES_LEAF = 2
MIN_IMPURITY_DECREASE=1e-6
MAX_LEAF_NODES = 150
MAX_FEATURES = 0.85


# Prediction horizons (hours ahead to predict)
PREDICTION_HORIZONS = list(range(1, 13))  # 1, 2, 3, ..., 12 hours


# ============================================================================
# FEATURE ENGINEERING FOR MULTI-HORIZON
# ============================================================================

def prepare_multi_horizon_data(df_raw):
    """
    Prepare data with multiple target variables (1h, 2h, ..., 12h ahead)
    """
    
    print("=" * 70)
    print("PREPARING MULTI-HORIZON TRAINING DATA")
    print("=" * 70)
    
    df = df_raw.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Temporal features
    print("\n[1/5] Creating temporal features...")
    df['hour'] = df['datetime'].dt.hour
    df['day_of_week'] = df['datetime'].dt.dayofweek
    df['day_of_month'] = df['datetime'].dt.day
    df['month'] = df['datetime'].dt.month
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    
    # Lag features
    print("[2/5] Creating lag features...")
    lag_hours = [1, 2, 3, 6, 12, 24]
    pollutants = ['pm2_5', 'pm10', 'no2', 'so2', 'co', 'o3']
    
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        for lag in lag_hours:
            df[f'{pollutant}_lag_{lag}h'] = df[col_name].shift(lag)
    
    for lag in lag_hours:
        df[f'aqi_lag_{lag}h'] = df['indian_aqi'].shift(lag)
    
    # Rolling statistics
    print("[3/5] Creating rolling statistics...")
    rolling_windows = [3, 6, 12, 24]
    
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        for window in rolling_windows:
            df[f'{pollutant}_rolling_mean_{window}h'] = df[col_name].rolling(window=window).mean()
            df[f'{pollutant}_rolling_std_{window}h'] = df[col_name].rolling(window=window).std()
    
    for window in rolling_windows:
        df[f'aqi_rolling_mean_{window}h'] = df['indian_aqi'].rolling(window=window).mean()
        df[f'aqi_rolling_std_{window}h'] = df['indian_aqi'].rolling(window=window).std()
    
    # Rate of change
    print("[4/5] Creating rate of change features...")
    for pollutant in pollutants:
        col_name = f'components.{pollutant}'
        df[f'{pollutant}_change_1h'] = df[col_name].diff(1)
        df[f'{pollutant}_change_3h'] = df[col_name].diff(3)
    
    df['aqi_change_1h'] = df['indian_aqi'].diff(1)
    df['aqi_change_3h'] = df['indian_aqi'].diff(3)
    
    # Create multiple target variables (1h to 12h ahead)
    print("[5/5] Creating target variables for each horizon...")
    for hours_ahead in PREDICTION_HORIZONS:
        df[f'target_aqi_{hours_ahead}h'] = df['indian_aqi'].shift(-hours_ahead)
    
    # Drop rows with NaN
    rows_before = len(df)
    df_clean = df.dropna().reset_index(drop=True)
    rows_after = len(df_clean)
    
    print(f"\n✓ Removed {rows_before - rows_after} rows with missing values")
    print(f"✓ Final dataset: {rows_after} samples")
    
    return df_clean


def get_feature_columns(df):
    """Get list of feature columns (excluding targets and metadata)"""
    
    exclude_patterns = ['target_', 'datetime', 'indian_aqi']
    feature_cols = [col for col in df.columns 
                   if not any(pattern in col for pattern in exclude_patterns)]
    
    # Ensure 'indian_aqi' is included as a feature (current AQI)
    if 'indian_aqi' in df.columns:
        feature_cols.append('indian_aqi')
    
    return feature_cols


# ============================================================================
# TRAINING FUNCTIONS
# ============================================================================

def train_model_for_horizon(X_train, y_train, X_test, y_test, hours_ahead):
    """Train a Random Forest model for a specific prediction horizon"""
    
    print(f"\n{'=' * 70}")
    print(f"TRAINING MODEL FOR {hours_ahead}H AHEAD")
    print(f"{'=' * 70}")
    
    # Initialize model
    model = RandomForestRegressor(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        min_samples_split=MIN_SAMPLES_SPLIT,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbose=0,
        max_features=MAX_FEATURES,
        max_leaf_nodes=MAX_LEAF_NODES,
        min_impurity_decrease=MIN_IMPURITY_DECREASE
        
    )
    

    # Train
    print(f"Training on {len(X_train)} samples...")
    model.fit(X_train, y_train)
    
    # Evaluate
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)
    
    train_mae = mean_absolute_error(y_train, y_train_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
    test_r2 = r2_score(y_test, y_test_pred)
    
    print(f"\nResults:")
    print(f"  Train MAE: {train_mae:.2f}")
    print(f"  Test MAE:  {test_mae:.2f}")
    print(f"  Test RMSE: {test_rmse:.2f}")
    print(f"  Test R²:   {test_r2:.4f}")
    
    metrics = {
        'hours_ahead': hours_ahead,
        'train_mae': float(train_mae),
        'test_mae': float(test_mae),
        'test_rmse': float(test_rmse),
        'test_r2': float(test_r2),
        'train_samples': len(X_train),
        'test_samples': len(X_test)
    }
    
    return model, metrics, y_test, y_test_pred


def train_all_models(df):
    """Train models for all prediction horizons"""
    
    print("\n" + "=" * 70)
    print("MULTI-HORIZON MODEL TRAINING")
    print("=" * 70)
    
    # Get features
    feature_cols = get_feature_columns(df)
    X = df[feature_cols]
    
    print(f"\nUsing {len(feature_cols)} features")
    print(f"Dataset: {len(df)} samples")
    
    # Save feature names
    feature_names_path = os.path.join(MODELS_DIR, 'feature_names.txt')
    with open(feature_names_path, 'w') as f:
        for feat in feature_cols:
            f.write(f"{feat}\n")
    print(f"✓ Saved feature names to {feature_names_path}")
    
    # Storage for results
    all_models = {}
    all_metrics = []
    
    # Train model for each horizon
    for hours_ahead in PREDICTION_HORIZONS:
        target_col = f'target_aqi_{hours_ahead}h'
        y = df[target_col]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, shuffle=False
        )
        
        # Train model
        model, metrics, y_test_actual, y_test_pred = train_model_for_horizon(
            X_train, y_train, X_test, y_test, hours_ahead
        )
        
        # Save model
        model_filename = f'aqi_rf_model_{hours_ahead}h.pkl'
        model_path = os.path.join(MODELS_DIR, model_filename)
        joblib.dump(model, model_path)
        print(f"✓ Saved model to {model_path}")
        
        # Store results
        all_models[hours_ahead] = {
            'model': model,
            'y_test': y_test_actual,
            'y_pred': y_test_pred
        }
        all_metrics.append(metrics)
    
    return all_models, all_metrics, feature_cols


# ============================================================================
# VISUALIZATION
# ============================================================================

def plot_metrics_comparison(metrics_list):
    """Plot comparison of metrics across different horizons"""
    
    horizons = [m['hours_ahead'] for m in metrics_list]
    test_mae = [m['test_mae'] for m in metrics_list]
    test_r2 = [m['test_r2'] for m in metrics_list]
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # MAE plot
    axes[0].plot(horizons, test_mae, marker='o', linewidth=2, markersize=8)
    axes[0].set_xlabel('Prediction Horizon (hours)', fontsize=12)
    axes[0].set_ylabel('Mean Absolute Error (MAE)', fontsize=12)
    axes[0].set_title('Prediction Error vs Horizon', fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xticks(horizons)
    
    # R² plot
    axes[1].plot(horizons, test_r2, marker='s', linewidth=2, markersize=8, color='green')
    axes[1].set_xlabel('Prediction Horizon (hours)', fontsize=12)
    axes[1].set_ylabel('R² Score', fontsize=12)
    axes[1].set_title('Model Performance vs Horizon', fontsize=14, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xticks(horizons)
    
    plt.tight_layout()
    plt.savefig(os.path.join(MODELS_DIR, 'metrics_comparison.png'), dpi=300)
    print(f"✓ Saved metrics comparison plot")
    plt.close()


def plot_sample_predictions(all_models, hours_to_plot=[1, 3, 6, 12]):
    """Plot actual vs predicted for selected horizons"""
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for idx, hours_ahead in enumerate(hours_to_plot):
        if hours_ahead in all_models:
            data = all_models[hours_ahead]
            y_test = data['y_test']
            y_pred = data['y_pred']
            
            # Sample 200 points for clarity
            sample_size = min(200, len(y_test))
            indices = np.arange(sample_size)
            
            axes[idx].plot(indices, y_test.iloc[:sample_size].values, 
                          label='Actual', linewidth=2, alpha=0.8)
            axes[idx].plot(indices, y_pred[:sample_size], 
                          label='Predicted', linewidth=2, alpha=0.8)
            axes[idx].set_xlabel('Sample Index', fontsize=11)
            axes[idx].set_ylabel('AQI', fontsize=11)
            axes[idx].set_title(f'{hours_ahead}h Ahead Predictions', 
                               fontsize=12, fontweight='bold')
            axes[idx].legend()
            axes[idx].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(MODELS_DIR, 'sample_predictions.png'), dpi=300)
    print(f"✓ Saved sample predictions plot")
    plt.close()


# ============================================================================
# MAIN TRAINING PIPELINE
# ============================================================================

def main():
    print("\n" + "=" * 70)
    print("MULTI-HORIZON AQI PREDICTION MODEL TRAINING")
    print("=" * 70)
    print(f"\nWill train {len(PREDICTION_HORIZONS)} models for horizons: {PREDICTION_HORIZONS}")
    
    # Load data
    print(f"\nLoading data from {DATA_FILE}...")
    df_raw = pd.read_csv(DATA_FILE)
    print(f"✓ Loaded {len(df_raw)} records")
    
    # Prepare data
    df_prepared = prepare_multi_horizon_data(df_raw)
    
    # Train all models
    all_models, all_metrics, feature_cols = train_all_models(df_prepared)
    
    # Save metrics
    metrics_path = os.path.join(MODELS_DIR, 'model_metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    print(f"\n✓ Saved metrics to {metrics_path}")
    
    # Create visualizations
    print("\nCreating visualizations...")
    plot_metrics_comparison(all_metrics)
    plot_sample_predictions(all_models)
    
    # Summary
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE!")
    print("=" * 70)
    print(f"\nTrained Models:")
    for metric in all_metrics:
        h = metric['hours_ahead']
        mae = metric['test_mae']
        r2 = metric['test_r2']
        print(f"  {h:2d}h ahead: MAE = {mae:5.2f}, R² = {r2:.4f}")
    
    avg_mae = np.mean([m['test_mae'] for m in all_metrics])
    avg_r2 = np.mean([m['test_r2'] for m in all_metrics])
    print(f"\nAverage Performance:")
    print(f"  MAE: {avg_mae:.2f}")
    print(f"  R²:  {avg_r2:.4f}")
    
    print(f"\nModels saved in: {MODELS_DIR}/")
    print("Files created:")
    print("  - aqi_rf_model_1h.pkl ... aqi_rf_model_12h.pkl")
    print("  - feature_names.txt")
    print("  - model_metrics.json")
    print("  - metrics_comparison.png")
    print("  - sample_predictions.png")
    
    return all_models, all_metrics


if __name__ == "__main__":
    models, metrics = main()