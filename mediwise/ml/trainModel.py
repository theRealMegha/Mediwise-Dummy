import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# Feature engineering logic from notebook
def add_extra_cbc_features(row):
    disease = row["Disease"]
    ranges = {
        "Iron Deficiency Anemia": [15, 20, 0.5, 1.5, 1, 4, 0, 1, 7, 10],
        "Hemolytic Anemia": [14, 19, 2.5, 6, 1, 4, 0, 1, 8, 11],
        "Macrocytic Anemia": [13, 18, 1, 2, 1, 4, 0, 1, 7, 10],
        "Thrombocytopenia": [12, 15, 0.5, 2, 1, 4, 0, 1, 10, 14],
        "Leukemia": [14, 18, 0.5, 2, 0, 2, 1, 3, 6, 9],
        "Infection": [12, 15, 0.5, 2, 4, 8, 0, 1, 7, 10]
    }
    r = ranges.get(disease, [11, 14, 0.5, 2, 1, 4, 0, 1, 7, 10])
    return pd.Series([np.random.uniform(r[i], r[i+1]) for i in range(0, 10, 2)])

def train():
    # Load your local dataset
    df = pd.read_csv("cbc_hematology_dataset.csv")

    # Enrich data
    df[["RDW", "RETIC%", "EOS%", "BASO%", "PLT_mean_volume"]] = df.apply(add_extra_cbc_features, axis=1)

    X = df.drop("Disease", axis=1)
    le = LabelEncoder()
    y = le.fit_transform(df["Disease"])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Initialize and train model
    model = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42, class_weight="balanced")
    model.fit(X_train, y_train)

    # Save artifacts
    joblib.dump(model, 'medical_model.pkl')
    joblib.dump(le, 'label_encoder.pkl')
    print("Training complete. Assets saved.")

if __name__ == "__main__":
    train()