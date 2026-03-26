import pandas as pd
import numpy as np
import random

def calculate_risk_index(age, sex, aqi, condition, symptoms, exposure, season, activity):
    """Calculate risk index based on research-backed logic"""
    
    # AQI contribution (0-40)
    if aqi <= 50: aqi_risk = 0
    elif aqi <= 100: aqi_risk = 5
    elif aqi <= 150: aqi_risk = 15
    elif aqi <= 200: aqi_risk = 25
    elif aqi <= 300: aqi_risk = 35
    else: aqi_risk = 40
    
    # Age vulnerability (0-20)
    if age < 5: age_risk = 20
    elif age < 15: age_risk = 15
    elif age < 30: age_risk = 5
    elif age < 60: age_risk = 8
    elif age < 75: age_risk = 15
    else: age_risk = 20
    
    # Pre-existing condition (0-25)
    condition_risk = condition * 2.5
    
    # Current symptoms (0-15)
    symptom_risk = symptoms * 1.5
    
    # Exposure (0-10)
    exposure_base = min(exposure / 12 * 10, 10)
    activity_multiplier = 1 + (activity * 0.3)
    exposure_risk = min(exposure_base * activity_multiplier, 10)
    
    # Total risk
    total_risk = aqi_risk + age_risk + condition_risk + symptom_risk + exposure_risk
    
    # Add small random variation (±5) for realism
    total_risk += random.uniform(-5, 5)
    
    # Clamp between 0-100
    return int(max(0, min(100, total_risk)))

def generate_dataset(n_samples=10000):
    """Generate synthetic dataset"""
    
    data = []
    
    for _ in range(n_samples):
        # Generate features with realistic distributions
        age = int(np.random.beta(2, 2) * 100)  # More people in middle ages
        sex = random.randint(0, 1)
        aqi = int(np.random.gamma(2, 50))  # Skewed towards lower values, but can be high
        aqi = min(aqi, 500)  # Cap at 500
        
        # Pre-existing conditions more common in elderly
        if age < 18:
            condition = random.choices([0,1,2,3,4,5], weights=[40,30,15,10,4,1])[0]
        elif age < 60:
            condition = random.choices([0,1,2,3,4,5,6], weights=[30,25,20,15,7,2,1])[0]
        else:
            condition = random.choices([0,1,2,3,4,5,6,7,8], weights=[10,15,20,20,15,10,5,3,2])[0]
        
        # Symptoms correlate with AQI
        if aqi < 100:
            symptoms = random.choices([0,1,2], weights=[80,15,5])[0]
        elif aqi < 200:
            symptoms = random.choices([0,1,2,3,4], weights=[30,30,20,15,5])[0]
        elif aqi < 300:
            symptoms = random.choices([2,3,4,5,6], weights=[20,25,30,20,5])[0]
        else:
            symptoms = random.choices([4,5,6,7,8], weights=[15,25,30,20,10])[0]
        
        exposure = round(random.uniform(0.5, 12.0), 1)
        season = random.randint(0, 3)
        activity = random.randint(0, 2)
        
        # Calculate risk index
        risk = calculate_risk_index(age, sex, aqi, condition, symptoms, 
                                    exposure, season, activity)
        
        data.append([age, sex, aqi, condition, symptoms, exposure, 
                     season, activity, risk])
    
    # Create DataFrame
    df = pd.DataFrame(data, columns=[
        'age', 'sex', 'aqi', 'pre_existing_condition', 'current_symptoms',
        'exposure_hours', 'season', 'activity_level', 'risk_index'
    ])
    
    return df

# Generate dataset
df = generate_dataset(10000)

# Save to CSV
df.to_csv('aqi_health_risk_dataset.csv', index=False)

print(f"Dataset created with {len(df)} samples")
print("\nFirst 5 rows:")
print(df.head())
print("\nDataset statistics:")
print(df.describe())