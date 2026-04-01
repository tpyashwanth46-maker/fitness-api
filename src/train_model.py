import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import shap
from sklearn.model_selection import cross_val_score, train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import numpy as np
import joblib

# ---------------- LOAD DATASETS ----------------

exercise = pd.read_csv("data/raw/exercise.csv")
calories = pd.read_csv("data/raw/calories.csv")

# ---------------- MERGE DATASETS ----------------

data = exercise.merge(calories, on="User_ID")
# ---------------- MERGE DATASETS ----------------

data = exercise.merge(calories, on="User_ID")


# ---------------- ADD NEW DATA FROM DATABASE ----------------

import sqlite3

try:
    conn = sqlite3.connect("fitness.db")
    new_data = pd.read_sql_query("SELECT * FROM fitness_data", conn)
    conn.close()

    if not new_data.empty:
        new_data = new_data.drop(columns=["id"])

        new_data = new_data.rename(columns={
            "age": "Age",
            "height": "Height",
            "weight": "Weight",
            "duration": "Duration",
            "heart_rate": "Heart_Rate",
            "body_temp": "Body_Temp",
            "calories": "Calories"
        })

        new_data["Duration"] = new_data["Duration"]
        new_data["Heart_Rate"] = new_data["Heart_Rate"]
        new_data["Body_Temp"] = new_data["Body_Temp"]

        new_data = new_data[["Age","Height","Weight","Duration","Heart_Rate","Body_Temp","Calories"]]

        data = pd.concat([data, new_data], ignore_index=True)

        print("\nNew database data added for training ✔")
        print("Final Dataset Shape:", data.shape)

except Exception as e:
    print("\nDatabase not found or error:", e)

# ---------------- FEATURE ENGINEERING ----------------

data["BMI"] = data["Weight"] / ((data["Height"] / 100) ** 2)

# ---------------- BASIC EDA ----------------

print("\nDataset Shape:")
print(data.shape)

print("\nDataset Columns:")
print(data.columns)

print("\nDataset Information:")
data.info()

print("\nStatistical Summary:")
print(data.describe())

print("\nMissing Values:")
print(data.isnull().sum())

# ---------------- VISUAL EDA ----------------
plt.figure(figsize=(6,4))
sns.scatterplot(x=data["Duration"], y=data["Calories"])
plt.title("Calories vs Duration")
plt.xlabel("Exercise Duration")
plt.ylabel("Calories Burned")
plt.savefig("reports/plots/duration_vs_calories.png")
plt.close()

plt.figure(figsize=(6,4))
sns.scatterplot(x=data["Heart_Rate"], y=data["Calories"])
plt.title("Heart Rate vs Calories")
plt.xlabel("Heart Rate")
plt.ylabel("Calories Burned")
plt.savefig("reports/plots/heartrate_vs_calories.png")
plt.close()

plt.figure(figsize=(6,4))
sns.scatterplot(x=data["BMI"], y=data["Calories"])
plt.title("BMI vs Calories")
plt.xlabel("BMI")
plt.ylabel("Calories Burned")
plt.savefig("reports/plots/bmi_vs_calories.png")
plt.close()

plt.figure(figsize=(8,6))
sns.heatmap(data.select_dtypes(include=['number']).corr(), annot=True, cmap="coolwarm")
plt.title("Feature Correlation Heatmap")
plt.savefig("reports/plots/correlation_heatmap.png")
plt.close()

# ---------------- OUTLIER REMOVAL ----------------

numeric_cols = data.select_dtypes(include=['number']).columns

for col in numeric_cols:
    Q1 = data[col].quantile(0.25)
    Q3 = data[col].quantile(0.75)
    IQR = Q3 - Q1

    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR

    data = data[(data[col] >= lower) & (data[col] <= upper)]

# ---------------- SELECT FEATURES ----------------

X = data[['Age','Height','Weight','Duration','Heart_Rate','Body_Temp','BMI']]
y = data['Calories']

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
    "n_estimators":[200,300,400],
    "learning_rate":[0.03,0.05,0.1],
    "max_depth":[4,6,8]
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

# ---------------- EVALUATION ----------------

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

# ---------------- SHAP MODEL EXPLANATION ----------------

print("\nGenerating SHAP explanation...")

explainer = shap.Explainer(model, X_train)

shap_values = explainer(X_test)

shap.summary_plot(shap_values, X_test)

# ---------------- FEATURE IMPORTANCE ----------------

importance = model.feature_importances_

plt.figure(figsize=(8,5))
plt.barh(X.columns, importance)
plt.title("Feature Importance for Calories Prediction")
plt.xlabel("Importance")
plt.ylabel("Features")
plt.show()

# ---------------- USER INPUT ----------------

print("\nEnter your exercise details")

age = float(input("Enter Age: "))
height = float(input("Enter Height (cm): "))
weight = float(input("Enter Weight (kg): "))
duration = float(input("Enter Exercise Duration (minutes): "))
heart_rate = float(input("Enter Heart Rate: "))
body_temp = float(input("Enter Body Temperature: "))

# ---------------- BMI ----------------

bmi = weight / ((height / 100) ** 2)

# ---------------- USER DATA ----------------

user_data = pd.DataFrame(
    [[age, height, weight, duration, heart_rate, body_temp, bmi]],
    columns=['Age','Height','Weight','Duration','Heart_Rate','Body_Temp','BMI']
)

# ---------------- PREDICTION ----------------

predicted_calories = model.predict(user_data)

print("\nYour BMI:", round(bmi,2))
print("Estimated Calories Burned:", predicted_calories[0])

print("\nEDA graphs saved in project folder.")

# ---------------- SAVE MODEL ----------------

joblib.dump(model, "models/calories_model.pkl")