"""
mongo_debug.py — Run this to find your queries in MongoDB Atlas
Place this file in your farmer_advisory folder (same level as manage.py)
Run with: python mongo_debug.py
"""

import os
import sys

# ── Set up Django settings so we can reuse your settings.py ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'farmer_advisory.settings')

try:
    import django
    django.setup()
    from django.conf import settings
    MONGODB_URI    = settings.MONGODB_URI
    MONGODB_DB_NAME = settings.MONGODB_DB_NAME
except Exception as e:
    # Fallback: paste your URI directly if Django setup fails
    print(f"⚠️  Django setup failed ({e}), using hardcoded URI")
    MONGODB_URI    = 'mongodb+srv://2410030267_db_user:Kundanika%2416@cluster0.do1lgqc.mongodb.net/?appName=Cluster0'
    MONGODB_DB_NAME = 'farmer_advisory_db'

from pymongo import MongoClient

print("\n" + "="*60)
print("🔍 FarmAI MongoDB Debug Tool")
print("="*60)

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
    client.admin.command('ping')
    print("✅ Connected to MongoDB Atlas successfully!\n")
except Exception as e:
    print(f"❌ CANNOT CONNECT TO MONGODB: {e}")
    print("\n⚠️  Possible reasons:")
    print("   1. Your IP is not whitelisted in Atlas Network Access")
    print("   2. Wrong password in MONGODB_URI")
    print("   3. No internet connection")
    sys.exit(1)

# ── List all databases ──
print("📂 ALL DATABASES in your Atlas account:")
dbs = client.list_database_names()
for db_name in dbs:
    print(f"   - {db_name}")

print(f"\n🎯 Your app uses database: '{MONGODB_DB_NAME}'")
db = client[MONGODB_DB_NAME]

# ── List all collections ──
print(f"\n📋 Collections inside '{MONGODB_DB_NAME}':")
cols = db.list_collection_names()
if not cols:
    print("   ⚠️  NO COLLECTIONS FOUND — database may be empty or wrong name!")
else:
    for col_name in cols:
        count = db[col_name].count_documents({})
        print(f"   - {col_name}  ({count} documents)")

# ── Check farmer_queries specifically ──
print("\n" + "="*60)
print("🌾 Checking 'farmer_queries' collection...")
print("="*60)

fq = db['farmer_queries']
total = fq.count_documents({})
print(f"Total documents in farmer_queries: {total}")

if total == 0:
    print("\n⚠️  ZERO documents found! Reasons could be:")
    print("   1. Queries are saving to IN-MEMORY fallback (not Atlas)")
    print("      → This happens if MongoDB connection fails during the query")
    print("   2. You're looking in the wrong database")
    print("      → Your app uses:", MONGODB_DB_NAME)
    print("   3. Data saved with farmer_id='anonymous'")
    print("      → Try logging IN before querying")
else:
    print(f"\n✅ Found {total} queries! Here are the last 5:\n")
    recent = list(fq.find({}).sort('timestamp', -1).limit(5))
    for i, q in enumerate(recent, 1):
        print(f"  Query {i}:")
        print(f"    farmer_id:      {q.get('farmer_id', 'N/A')}")
        print(f"    query_text:     {q.get('query_text', 'N/A')[:60]}")
        print(f"    detected_stress: {q.get('detected_stress', 'N/A')}")
        print(f"    timestamp:      {q.get('timestamp', 'N/A')}")
        print()

# ── Check by farmer_id ──
print("="*60)
print("👤 Checking by farmer_id...")
print("="*60)
farmer_ids = fq.distinct('farmer_id')
print(f"Unique farmer_ids in the collection: {farmer_ids}")

if 'anonymous' in farmer_ids:
    anon_count = fq.count_documents({'farmer_id': 'anonymous'})
    print(f"\n⚠️  WARNING: {anon_count} queries saved as 'anonymous'")
    print("   This means the queries were made WITHOUT being logged in.")
    print("   Solution: Log in to the system FIRST, then ask a question.")

print("\n" + "="*60)
print("📊 All farmer_ids and their query counts:")
pipeline = [
    {"$group": {"_id": "$farmer_id", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
for doc in fq.aggregate(pipeline):
    print(f"   {doc['_id']}:  {doc['count']} queries")

print("\n" + "="*60)
print("✅ Debug complete! Check the output above.")
print("="*60)
print("\n📌 HOW TO SEE YOUR QUERIES IN ATLAS:")
print(f"   1. Go to: atlas.mongodb.com")
print(f"   2. Click your cluster → Browse Collections")
print(f"   3. Database: {MONGODB_DB_NAME}")
print(f"   4. Collection: farmer_queries")
print(f"   5. Click REFRESH button (↺) in Atlas")
print(f"   6. Filter box: {{\"farmer_id\": \"YOUR_EMAIL@gmail.com\"}}")
