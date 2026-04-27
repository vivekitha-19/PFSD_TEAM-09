"""
ML Classification Engine v4 — FarmAI
======================================
Priority order:
  1. Load real trained model from ml_model/model.pkl (if user ran train_model.py)
  2. Fall back to synthetic ensemble (NB+LR+DT) if no real model found

This means: run train_model.py → your real CSV-trained model is used automatically.
No server restart needed if you use the /api/retrain/ endpoint.
"""
import os
import logging
import pickle
import json
import numpy as np
from typing import Dict, List

logger = logging.getLogger(__name__)

try:
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.model_selection import train_test_split
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("⚠️  Scikit-learn not available")

# Path to real trained model (from ml_model/train_model.py)
REAL_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'ml_model', 'model.pkl'
)
REAL_MODEL_INFO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'ml_model', 'model_info.json'
)

# Labels used by both real and synthetic models
STRESS_LABELS = [
    'bacterial_disease', 'fungal_disease', 'heat_stress',
    'nutrient_deficiency', 'pest_infestation', 'viral_disease',
    'water_stress', 'weed_infestation'
]

# Map CSV label keys → internal uppercase keys (kept for advisory lookup)
LABEL_TO_STRESS = {
    'bacterial_disease':  'BACTERIAL_DISEASE',
    'fungal_disease':     'FUNGAL_DISEASE',
    'heat_stress':        'HEAT_STRESS',
    'nutrient_deficiency':'NUTRIENT_DEFICIENCY',
    'pest_infestation':   'PEST_INFESTATION',
    'viral_disease':      'VIRAL_DISEASE',
    'water_stress':       'WATER_STRESS',
    'weed_infestation':   'WEED_INFESTATION',
}

STRESS_DISPLAY = {
    'BACTERIAL_DISEASE':  '🧫 Bacterial Disease',
    'FUNGAL_DISEASE':     '🍄 Fungal Disease',
    'HEAT_STRESS':        '🌡️ Heat Stress',
    'NUTRIENT_DEFICIENCY':'🌿 Nutrient Deficiency',
    'PEST_INFESTATION':   '🐛 Pest Infestation',
    'VIRAL_DISEASE':      '🦠 Viral Disease',
    'WATER_STRESS':       '💧 Water/Drought Stress',
    'WEED_INFESTATION':   '🌱 Weed Infestation',
}

SEVERITY_MAP = {
    'BACTERIAL_DISEASE':  'High',
    'FUNGAL_DISEASE':     'High',
    'HEAT_STRESS':        'Medium',
    'NUTRIENT_DEFICIENCY':'Medium',
    'PEST_INFESTATION':   'High',
    'VIRAL_DISEASE':      'Very High',
    'WATER_STRESS':       'High',
    'WEED_INFESTATION':   'Medium',
}

COLOR_MAP = {
    'BACTERIAL_DISEASE':  '#b91c1c',
    'FUNGAL_DISEASE':     '#8b5cf6',
    'HEAT_STRESS':        '#f97316',
    'NUTRIENT_DEFICIENCY':'#f59e0b',
    'PEST_INFESTATION':   '#ef4444',
    'VIRAL_DISEASE':      '#dc2626',
    'WATER_STRESS':       '#3b82f6',
    'WEED_INFESTATION':   '#65a30d',
}


class RealModelClassifier:
    """
    Wraps the real trained sklearn Pipeline (TF-IDF + LogReg)
    from ml_model/model.pkl — trained on training_data.csv
    """
    def __init__(self, pipeline, model_info=None):
        self.pipeline   = pipeline
        self.model_info = model_info or {}
        self.accuracy   = model_info.get('accuracy', 0) if model_info else 0
        logger.info(f"✅ Real trained model loaded | Accuracy: {self.accuracy:.2%} | "
                    f"Samples: {model_info.get('total_samples', '?')}")

    def predict(self, text: str) -> Dict:
        """Predict from raw text using TF-IDF pipeline (no feature vector needed)"""
        try:
            label      = self.pipeline.predict([text])[0]
            proba      = self.pipeline.predict_proba([text])[0]
            confidence = float(max(proba))
            stress_key = LABEL_TO_STRESS.get(label, 'FUNGAL_DISEASE')

            return {
                'predicted_stress':   stress_key,
                'display_name':       STRESS_DISPLAY.get(stress_key, stress_key),
                'confidence':         round(confidence, 4),
                'confidence_percent': f"{confidence*100:.1f}%",
                'severity':           SEVERITY_MAP.get(stress_key, 'Medium'),
                'color':              COLOR_MAP.get(stress_key, '#6b7280'),
                'model_used':         f"TF-IDF+LogReg (real data, {self.model_info.get('total_samples','?')} samples)",
                'model_accuracy':     f"{self.accuracy:.1%}",
                'insufficient_data':  False,
            }
        except Exception as e:
            logger.error(f"Real model predict error: {e}")
            return self._insufficient()

    def _insufficient(self):
        return {
            'predicted_stress':'INSUFFICIENT_DATA','display_name':'❓ Insufficient Information',
            'confidence':0.0,'confidence_percent':'0%','severity':'Unknown',
            'color':'#6b7280','model_used':'N/A','insufficient_data':True
        }


class SyntheticEnsembleClassifier:
    """
    Fallback when no real model.pkl found.
    Uses NB+LR+DT ensemble on synthetic feature vectors.
    """
    def __init__(self):
        self.nb_model = None
        self.lr_model = None
        self.dt_model = None
        self.is_trained = False
        self._pkl = os.path.join(os.path.dirname(__file__), 'synthetic_model.pkl')
        self._load_or_train()

    def _load_or_train(self):
        if os.path.exists(self._pkl):
            try:
                with open(self._pkl, 'rb') as f:
                    s = pickle.load(f)
                if len(s.get('nb').classes_) == len(STRESS_LABELS):
                    self.nb_model = s['nb']; self.lr_model = s['lr']; self.dt_model = s['dt']
                    self.is_trained = True
                    logger.info("✅ Synthetic ensemble loaded"); return
            except Exception as e:
                logger.warning(f"Synthetic load failed: {e}")
        self._train()

    def _train(self):
        if not SKLEARN_AVAILABLE: return
        X, y = self._make_data()
        Xs = (X * 100).astype(int)
        Xt, Xte, yt, yte = train_test_split(Xs, y, test_size=.2, random_state=42, stratify=y)
        self.nb_model = MultinomialNB(alpha=.5).fit(Xt, yt)
        self.lr_model = LogisticRegression(max_iter=500, random_state=42).fit(Xt, yt)
        self.dt_model = DecisionTreeClassifier(max_depth=12, random_state=42).fit(Xt, yt)
        self.is_trained = True
        nb_a = self.nb_model.score(Xte, yte)
        lr_a = self.lr_model.score(Xte, yte)
        dt_a = self.dt_model.score(Xte, yte)
        logger.info(f"✅ Synthetic ensemble | NB:{nb_a:.2%} LR:{lr_a:.2%} DT:{dt_a:.2%}")
        try:
            with open(self._pkl, 'wb') as f:
                pickle.dump({'nb':self.nb_model,'lr':self.lr_model,'dt':self.dt_model}, f)
        except Exception: pass

    def _make_data(self):
        np.random.seed(42)
        # Feature order: BACTERIAL, FUNGAL, HEAT, NUTRIENT, PEST, VIRAL, WATER, WEED
        templates = [
            ([.9,.1,0,0,0,0,.1,0],'bacterial_disease',90),([.1,.9,0,.1,0,0,0,0],'fungal_disease',90),
            ([0,0,.9,.1,0,0,.2,0],'heat_stress',90),      ([0,.1,0,.9,0,.1,0,0],'nutrient_deficiency',90),
            ([0,0,0,0,.9,.1,0,0],'pest_infestation',90),  ([0,.1,0,.1,0,.9,0,0],'viral_disease',90),
            ([0,0,.2,0,0,0,.9,0],'water_stress',90),      ([0,0,0,.1,0,0,0,.9],'weed_infestation',90),
        ]
        X, y = [], []
        for base, lbl, n in templates:
            b = np.array(base)
            for _ in range(n):
                X.append(np.clip(b + np.random.normal(0,.04,len(b)), 0, 1)); y.append(lbl)
        return np.array(X), y

    def predict_from_features(self, fv: List[float]) -> Dict:
        if not fv or max(fv) < 0.05:
            return self._insufficient()
        arr = np.clip((np.array(fv).reshape(1,-1)*100).astype(int), 0, None)
        proba = np.zeros(len(STRESS_LABELS))
        for mdl, w in [(self.nb_model,.3),(self.lr_model,.4),(self.dt_model,.3)]:
            if mdl is None: continue
            try:
                p = mdl.predict_proba(arr)[0]
                for i, lbl in enumerate(STRESS_LABELS):
                    if lbl in mdl.classes_:
                        proba[i] += p[list(mdl.classes_).index(lbl)] * w
            except Exception: pass
        best = int(np.argmax(proba))
        lbl  = STRESS_LABELS[best]
        conf = min(0.55 + float(proba[best]) * 0.42, 0.97)
        key  = LABEL_TO_STRESS.get(lbl, 'FUNGAL_DISEASE')
        return {
            'predicted_stress':   key,
            'display_name':       STRESS_DISPLAY.get(key, key),
            'confidence':         round(conf, 4),
            'confidence_percent': f"{conf*100:.1f}%",
            'severity':           SEVERITY_MAP.get(key,'Medium'),
            'color':              COLOR_MAP.get(key,'#6b7280'),
            'model_used':         'NB+LR+DT Ensemble (synthetic)',
            'model_accuracy':     'N/A',
            'insufficient_data':  False,
        }

    def _insufficient(self):
        return {
            'predicted_stress':'INSUFFICIENT_DATA','display_name':'❓ Insufficient Information',
            'confidence':0.0,'confidence_percent':'0%','severity':'Unknown',
            'color':'#6b7280','model_used':'N/A','insufficient_data':True
        }


# ─── Master Classifier ────────────────────────────────────────────────────────

class CropStressClassifier:
    """
    Master classifier. Uses real trained model if available, else synthetic.
    Call .predict(text, feature_vector) — text used by real model, fv by synthetic.
    """

    def __init__(self):
        self.real_model      = None
        self.synthetic_model = None
        self.using_real      = False
        self.is_trained      = True
        self._load()

    def _load(self):
        # Try real trained model first
        if os.path.exists(REAL_MODEL_PATH) and SKLEARN_AVAILABLE:
            try:
                pipeline = joblib.load(REAL_MODEL_PATH)
                info = {}
                if os.path.exists(REAL_MODEL_INFO):
                    with open(REAL_MODEL_INFO) as f:
                        info = json.load(f)
                self.real_model  = RealModelClassifier(pipeline, info)
                self.using_real  = True
                logger.info(f"🎯 Using REAL trained model: {REAL_MODEL_PATH}")
                return
            except Exception as e:
                logger.warning(f"Real model load failed: {e}")

        # Fallback to synthetic
        logger.info("📦 Real model not found — using synthetic ensemble")
        logger.info("   Run: cd ml_model && python train_model.py  to train real model")
        self.synthetic_model = SyntheticEnsembleClassifier()
        self.using_real      = False

    def reload(self):
        """Hot-reload model without server restart (called after retraining)"""
        self.real_model  = None
        self.using_real  = False
        self._load()
        return self.using_real

    def predict(self, feature_vector: List[float], raw_text: str = '') -> Dict:
        """
        Predict crop stress.
        If real model is loaded: uses raw_text with TF-IDF pipeline.
        If synthetic: uses feature_vector (from NLP engine).
        """
        if self.using_real and self.real_model and raw_text:
            result = self.real_model.predict(raw_text)
        elif self.synthetic_model:
            result = self.synthetic_model.predict_from_features(feature_vector)
        else:
            result = {
                'predicted_stress':'INSUFFICIENT_DATA','display_name':'❓ Model Not Available',
                'confidence':0.0,'confidence_percent':'0%','severity':'Unknown',
                'color':'#6b7280','model_used':'None','insufficient_data':True
            }

        result['model_source'] = 'real_csv_trained' if self.using_real else 'synthetic_ensemble'
        return result

    def get_model_info(self) -> Dict:
        if self.using_real and self.real_model:
            return {
                'type':     'Real CSV-trained',
                'accuracy': self.real_model.accuracy,
                'info':     self.real_model.model_info
            }
        return {'type': 'Synthetic Ensemble', 'accuracy': 0, 'info': {}}


ml_classifier = CropStressClassifier()
logger.info(f"✅ ML Classifier v4 ready | Source: {'Real CSV model' if ml_classifier.using_real else 'Synthetic ensemble'}")
