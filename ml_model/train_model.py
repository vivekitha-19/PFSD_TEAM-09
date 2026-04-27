"""
FarmAI — ML Model Training Script
===================================
Uses TF-IDF + Logistic Regression pipeline (as per patent spec).
Supports English + Hindi + Telugu multilingual training data.

HOW TO RUN:
    cd farmer_advisory/ml_model
    python train_model.py

To retrain after adding new rows to training_data.csv:
    python train_model.py

Output:
    model.pkl           ← main trained model
    vectorizer_info.txt ← feature info for reference
"""

import os
import sys
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score
import joblib
import json

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH    = os.path.join(SCRIPT_DIR, "training_data.csv")
MODEL_PATH   = os.path.join(SCRIPT_DIR, "model.pkl")
INFO_PATH    = os.path.join(SCRIPT_DIR, "model_info.json")


def load_data():
    print(f"\n📂 Loading dataset from: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    print(f"   ✅ {len(df)} rows loaded")
    print(f"   📊 Labels: {df['label'].value_counts().to_dict()}")
    # Drop empty rows
    df = df.dropna(subset=['text','label'])
    df['text'] = df['text'].astype(str).str.strip()
    df = df[df['text'] != '']
    print(f"   ✅ {len(df)} rows after cleaning")
    return df


def train(df):
    X = df['text']
    y = df['label']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"\n🔀 Train: {len(X_train)} | Test: {len(X_test)}")

    # ── TF-IDF + Logistic Regression (primary model) ──
    lr_pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            ngram_range=(1, 2),    # unigrams + bigrams
            max_features=5000,
            sublinear_tf=True,
            analyzer='word',
            token_pattern=r'(?u)\b\w+\b'   # handles unicode (Hindi/Telugu)
        )),
        ('clf', LogisticRegression(
            max_iter=500,
            C=1.5,
            solver='lbfgs',
            random_state=42
        ))
    ])

    lr_pipeline.fit(X_train, y_train)
    lr_acc = accuracy_score(y_test, lr_pipeline.predict(X_test))
    print(f"\n🤖 Logistic Regression accuracy: {lr_acc:.2%}")

    # ── Cross-validation score ──
    cv_scores = cross_val_score(lr_pipeline, X, y, cv=5, scoring='accuracy')
    print(f"📊 5-fold CV accuracy: {cv_scores.mean():.2%} ± {cv_scores.std():.2%}")

    # ── Full classification report ──
    y_pred = lr_pipeline.predict(X_test)
    print("\n📋 Classification Report:")
    print(classification_report(y_test, y_pred))

    # ── Save model ──
    joblib.dump(lr_pipeline, MODEL_PATH)
    print(f"\n✅ Model saved to: {MODEL_PATH}")

    # ── Save model info ──
    info = {
        "accuracy":       round(lr_acc, 4),
        "cv_accuracy":    round(cv_scores.mean(), 4),
        "cv_std":         round(cv_scores.std(), 4),
        "total_samples":  len(df),
        "train_samples":  len(X_train),
        "test_samples":   len(X_test),
        "labels":         sorted(y.unique().tolist()),
        "label_counts":   df['label'].value_counts().to_dict(),
        "features":       lr_pipeline.named_steps['tfidf'].max_features,
        "ngram_range":    list(lr_pipeline.named_steps['tfidf'].ngram_range),
        "model_type":     "TF-IDF + LogisticRegression",
        "model_path":     MODEL_PATH,
    }
    with open(INFO_PATH, 'w') as f:
        json.dump(info, f, indent=2)
    print(f"📄 Model info saved to: {INFO_PATH}")
    return lr_pipeline, info


if __name__ == "__main__":
    print("=" * 55)
    print("  FarmAI — ML Model Training")
    print("=" * 55)
    df = load_data()
    model, info = train(df)
    print("\n" + "=" * 55)
    print(f"  ✅ TRAINING COMPLETE")
    print(f"  Accuracy : {info['accuracy']:.2%}")
    print(f"  CV Score : {info['cv_accuracy']:.2%}")
    print(f"  Labels   : {len(info['labels'])} classes")
    print(f"  Samples  : {info['total_samples']}")
    print("=" * 55)
    print("\n  To retrain: add rows to training_data.csv → python train_model.py")
    print("  Model auto-loads in FarmAI on next server restart.")
