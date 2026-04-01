print("THIS IS NEW FILE")
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import shap
import os
print("Running file path:", os.path.abspath(__file__))
from sklearn.model_selection import cross_val_score, train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import joblib
import numpy as np

# ---------------- LOAD DATASET ----------------

data= pd.read_csv("data/raw/bodyPerformance.csv")
# ---------------- LOAD NEW DATA FROM DATABASE ----------------

import sqlite3

try:
    conn = sqlite3.connect("fitness.db")
    new_data = pd.read_sql_query("SELECT * FROM fitness_data", conn)
    conn.close()

    if not new_data.empty:

        # Rename columns to match dataset
        new_data = new_data.rename(columns={
            "gender": "gender",
            "body_fat": "body fat_%",
            "diastolic": "diastolic",
            "systolic": "systolic",
            "grip": "gripForce",
            "flexibility": "sit and bend forward_cm",
            "situps": "sit-ups counts",
            "jump": "broad jump_cm"
        })

        # Select only required columns
        new_data = new_data[
            [
                "gender",
                "body fat_%",
                "diastolic",
                "systolic",
                "gripForce",
                "sit and bend forward_cm",
                "sit-ups counts",
                "broad jump_cm"
            ]
        ]

        # Combine old + new data
        data = pd.concat([data, new_data], ignore_index=True)

        print("\nNew DB data added to bio model training ✔")

except Exception as e:
    print("\nDB load error:", e)

print("\nFirst rows of dataset:")
print(data.head())
# ---------------- HANDLE MISSING VALUES ----------------
data = data.fillna(data.mean(numeric_only=True))

# ---------------- REMOVE UNUSED COLUMN ----------------

data = data.drop(columns=["class"])

# ---------------- CONVERT GENDER TO NUMERIC ----------------

data["gender"] = data["gender"].map({"M": 1, "F": 0})
data["gender"] = data["gender"].fillna(0)



print("\nSample Biological Age Values:")
print(data[["age"]].head())

# ---------------- EDA VISUALIZATION ----------------

plt.figure(figsize=(6,4))
sns.scatterplot(x=data["body fat_%"], y=data["age"])
plt.title("Body Fat vs Biological Age")
plt.xlabel("Body Fat %")
plt.ylabel("Biological Age")
plt.savefig("reports/plots/bodyfat_vs_bioage.png")
plt.close()

plt.figure(figsize=(6,4))
sns.scatterplot(x=data["gripForce"], y=data["age"])
plt.title("Grip Strength vs Biological Age")
plt.xlabel("Grip Strength")
plt.ylabel("Biological Age")
plt.savefig("reports/plots/grip_vs_bioage.png")
plt.close()

plt.figure(figsize=(6,4))
sns.scatterplot(x=data["sit-ups counts"], y=data["age"])
plt.title("Sit-ups vs Biological Age")
plt.xlabel("Sit-ups Count")
plt.ylabel("Biological Age")
plt.savefig("reports/plots/situps_vs_bioage.png")
plt.close()

plt.figure(figsize=(10,8))
sns.heatmap(data.select_dtypes(include=['number']).corr(), annot=True, cmap="coolwarm")
plt.title("Feature Correlation Heatmap")
plt.savefig("reports/plots/bioage_correlation_heatmap.png")
plt.close()

print("\nEDA graphs saved in reports/plots folder.")
# ---------------- SELECT FEATURES ----------------

X = data[
    [
        "gender",
        "body fat_%",
        "diastolic",
        "systolic",
        "gripForce",
        "sit and bend forward_cm",
        "sit-ups counts",
        "broad jump_cm"
    ]
]

y = data["age"]

# ---------------- TRAIN TEST SPLIT ----------------

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ---------------- MODELS ----------------

rf_model = RandomForestRegressor(
    n_estimators=200,
    max_depth=12,
    random_state=42
)

gb_model = GradientBoostingRegressor(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=4,
    random_state=42
)

# ---------------- XGBOOST HYPERPARAMETER TUNING ----------------

param_grid = {
    "n_estimators": [200,300,400],
    "learning_rate": [0.03,0.05,0.1],
    "max_depth": [4,6,8]
}

xgb_base = XGBRegressor(random_state=42)

grid = GridSearchCV(
    estimator=xgb_base,
    param_grid=param_grid,
    cv=5,
    scoring="r2",
    n_jobs=-1
)

print("\nTuning XGBoost model...")

grid.fit(X_train, y_train)

xgb_model = grid.best_estimator_

print("Best XGBoost Parameters:", grid.best_params_)

# ---------------- TRAIN OTHER MODELS ----------------

rf_model.fit(X_train, y_train)
gb_model.fit(X_train, y_train)

# ---------------- CROSS VALIDATION ----------------

rf_scores = cross_val_score(rf_model, X, y, cv=5, scoring="r2")
gb_scores = cross_val_score(gb_model, X, y, cv=5, scoring="r2")
xgb_scores = cross_val_score(xgb_model, X, y, cv=5, scoring="r2")

print("\nRandom Forest CV R2 Scores:", rf_scores)
print("Random Forest Avg R2:", round(rf_scores.mean(),3))

print("\nGradient Boosting CV R2 Scores:", gb_scores)
print("Gradient Boosting Avg R2:", round(gb_scores.mean(),3))

print("\nXGBoost CV R2 Scores:", xgb_scores)
print("XGBoost Avg R2:", round(xgb_scores.mean(),3))

# ---------------- PREDICTIONS ----------------

rf_pred = rf_model.predict(X_test)
gb_pred = gb_model.predict(X_test)
xgb_pred = xgb_model.predict(X_test)

# ---------------- EVALUATION FUNCTION ----------------

def evaluate(name, y_true, pred):

    mae = mean_absolute_error(y_true, pred)
    rmse = np.sqrt(mean_squared_error(y_true, pred))
    r2 = r2_score(y_true, pred)

    print("\n------", name, "------")
    print("MAE :", round(mae,2))
    print("RMSE:", round(rmse,2))
    print("R2 Score:", round(r2,3))

    return r2


rf_r2 = evaluate("Random Forest", y_test, rf_pred)
gb_r2 = evaluate("Gradient Boosting", y_test, gb_pred)
xgb_r2 = evaluate("XGBoost (Tuned)", y_test, xgb_pred)

# ---------------- BEST MODEL SELECTION ----------------

best_score = max(rf_r2, gb_r2, xgb_r2)

if best_score == rf_r2:
    model = rf_model
    print("\nBest Model Selected: Random Forest")

elif best_score == gb_r2:
    model = gb_model
    print("\nBest Model Selected: Gradient Boosting")

else:
    model = xgb_model
    print("\nBest Model Selected: Tuned XGBoost")
# ---------------- ACTUAL VS PREDICTED PLOT ----------------

best_pred = model.predict(X_test)

plt.figure(figsize=(6,6))

plt.scatter(y_test, best_pred)

plt.xlabel("Actual Calories")
plt.ylabel("Predicted Calories")

plt.title("Actual vs Predicted Calories")

plt.show()


# ---------------- RESIDUAL PLOT ----------------

residuals = y_test - best_pred

plt.figure(figsize=(6,4))

plt.scatter(best_pred, residuals)

plt.xlabel("Predicted Calories")
plt.ylabel("Residual Error")

plt.title("Residual Plot")

plt.axhline(y=0)

plt.show()
# ---------------- SHAP MODEL EXPLANATION ----------------

print("\nGenerating SHAP explanation...")

explainer = shap.Explainer(model, X_train)

shap_values = explainer(X_test)

shap.summary_plot(shap_values, X_test)

# ---------------- FEATURE IMPORTANCE ----------------

importance = model.feature_importances_

plt.figure(figsize=(8,5))
plt.barh(X.columns, importance)
plt.title("Feature Importance for Biological Age Prediction")
plt.xlabel("Importance")
plt.ylabel("Features")
plt.show()

# ---------------- SAVE MODEL ----------------

joblib.dump(model, "models/bio_age_model.pkl")

print("\nBiological age model saved successfully.")