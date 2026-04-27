# 🌾 Farmer Crop Stress Detection & Advisory System
### AI-Powered Agriculture Platform | Django + MongoDB + GraphQL + NLP + ML

---

## 📦 PACKAGES TO INSTALL (Run this FIRST)

Open terminal in PyCharm and run:

```bash
pip install Django==4.2.7 graphene-django==3.1.5 pymongo==4.6.1 nltk==3.8.1 scikit-learn==1.3.2 numpy==1.26.2 pandas==2.1.4 joblib==1.3.2 django-cors-headers==4.3.1 python-dotenv==1.0.0 whitenoise==6.6.0
```

Or install all at once:
```bash
pip install -r requirements.txt
```

---

## ▶️ HOW TO RUN IN PYCHARM

### Method 1 — One-Click Run (Recommended)
1. Open `run_server.py` in PyCharm
2. Right-click → **Run 'run_server'**
3. Open browser: **http://127.0.0.1:8000**

### Method 2 — Terminal Commands
```bash
cd farmer_advisory
python manage.py migrate
python manage.py runserver
```

---

## 🔗 System URLs

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000 | Farmer Dashboard (Main UI) |
| http://127.0.0.1:8000/graphql/ | GraphQL API Explorer |
| http://127.0.0.1:8000/health/ | System Health Check |
| http://127.0.0.1:8000/api/process-query/ | REST API Fallback |

---

## 🗄️ MongoDB Setup (Optional)

The system works WITHOUT MongoDB using in-memory storage.

To use MongoDB:
1. Install MongoDB Community: https://www.mongodb.com/try/download/community
2. Start MongoDB service: `mongod`
3. Edit `.env` file: Set `MONGODB_URI=mongodb://localhost:27017/`

For cloud MongoDB Atlas:
```
MONGODB_URI=mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/
```

---

## ⚡ GraphQL API Examples

Open http://127.0.0.1:8000/graphql/ and try:

### Submit a Farmer Query (Main Mutation)
```graphql
mutation {
  submitFarmerQuery(queryText: "My rice leaves are turning yellow") {
    success
    mlResult {
      displayName
      confidence
      severity
      color
    }
    advisory {
      title
      immediateAction
      treatment
      prevention
      fertilizers
    }
    nlpResult {
      detectedCrop
      filteredTokens
    }
  }
}
```

### Fetch All Crops
```graphql
query {
  allCrops {
    name
    season
    commonDiseases
  }
}
```

### Get Query History
```graphql
query {
  queryHistory(limit: 5) {
    queryText
    detectedStress
    timestamp
  }
}
```

---

## 🏗️ Project Structure

```
farmer_advisory/
├── manage.py                    ← Django management
├── run_server.py                ← ONE-CLICK RUN for PyCharm
├── requirements.txt             ← All pip packages
├── .env                         ← MongoDB config
│
├── farmer_advisory/             ← Django project config
│   ├── settings.py              ← All settings
│   ├── urls.py                  ← URL routing
│   ├── schema.py                ← Root GraphQL schema
│   └── wsgi.py
│
├── advisory/                    ← Main Django app
│   ├── views.py                 ← Dashboard + REST API
│   ├── urls.py                  ← App URLs
│   ├── schema.py                ← GraphQL types + resolvers
│   ├── apps.py                  ← App startup + DB seeding
│   └── templates/advisory/
│       └── dashboard.html       ← Full farmer UI (Voice+Dashboard)
│
├── nlp_engine/                  ← NLP Processing Module
│   ├── nlp_processor.py         ← Text cleaning, tokenization, lemmatization
│   └── __init__.py
│
├── ml_engine/                   ← Machine Learning Module
│   ├── ml_classifier.py         ← Naive Bayes + LogReg + Decision Tree
│   ├── trained_model.pkl        ← Auto-generated model file
│   └── __init__.py
│
└── db_connector/                ← MongoDB Connector
    ├── mongo_db.py              ← All DB operations + seed data
    └── __init__.py
```

---

## 🧠 AI/ML Pipeline

```
Farmer Voice/Text Input
        ↓
Web Speech API (voice→text)
        ↓
NLP Processor (NLTK/SpaCy)
  • Text cleaning & normalization
  • Tokenization
  • Stopword removal
  • Lemmatization
  • Feature extraction
        ↓
ML Classifier (Scikit-learn Ensemble)
  • Naive Bayes (30% weight)
  • Logistic Regression (40% weight)
  • Decision Tree (30% weight)
        ↓
AI Advisory Engine
  • Fetch advisory from MongoDB
  • Generate treatment plan
        ↓
GraphQL Response → Dashboard UI
```

---

## 🌐 Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 4.2 (Python) |
| Database | MongoDB (pymongo) |
| API | GraphQL (graphene-django) |
| NLP | NLTK |
| ML | Scikit-learn (NB + LR + DT Ensemble) |
| Frontend | HTML5 + CSS3 + JavaScript |
| Voice | Web Speech API |
| Python | 3.9+ |

---

## 🌿 Supported Crop Stress Types

1. **Nutrient Deficiency** — Yellowing, pale leaves
2. **Fungal Disease** — White powder, brown spots, rust
3. **Water Stress** — Wilting, drying, drooping
4. **Pest Infestation** — Holes, insects, caterpillars
5. **Viral Disease** — Mosaic patterns, leaf curl
6. **Bacterial Disease** — Water-soaked lesions, rot
7. **Heat Stress** — Scorching, bleaching, tip burn
8. **Healthy** — No stress detected

---

## 🇮🇳 Supported Languages (Voice)

English, Hindi, Telugu, Tamil, Kannada, Marathi, Punjabi

---

*Patent-level Agricultural AI System | Developed for Farmers of India*
