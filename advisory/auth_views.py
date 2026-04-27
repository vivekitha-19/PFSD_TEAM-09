"""
Authentication + Per-User Analytics Views – FarmAI v4

Changes from v3:
  ✅ FIX #1 — save_farmer_query now uses farmer_id from session correctly
              (was only falling back to request body; now always uses session email when logged in)
  ✅ FIX #2 — profile_data_api adds hour-of-day usage breakdown (peak hours)
              using MongoDB $group + $project + $substr on timestamp
  ✅ FIX #3 — analytics_data_api is now per-user only (filters by farmer_id)
  ✅ FIX #4 — analytics page removed; analytics data merged into profile_data_api
  ✅ FIX #5 — auth_urls.py: analytics/ and analytics/data/ routes kept for
              backward compat but now serve per-user data only

MongoDB features used:
  ✅ $facet       — parallel sub-pipelines (total / today / week / crops)
  ✅ $group       — stress breakdown, hour-of-day, crop distribution
  ✅ $project     — computed fields ($substr, $toInt on timestamp hour)
  ✅ $bucket      — confidence score distribution
  ✅ $sort, $limit — top-N results
  ✅ $match       — filter by farmer_id (per-user scope)
  ✅ $lookup      — (kept in user_activity for admin use, but profile is own data)
"""
import json
import logging
import hashlib
import os
import re
from datetime import datetime, timedelta
from functools import wraps

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import get_token

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hash_password(raw: str) -> str:
    salt = os.environ.get("PASSWORD_SALT", "farmai_salt_2024")
    return hashlib.sha256((salt + raw).encode()).hexdigest()


def _get_db():
    try:
        from db_connector.mongo_db import get_db_connection
        return get_db_connection()
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}")
    return None


def _col(name):
    db = _get_db()
    return db[name] if db is not None else None


def _get_current_user(request):
    email = request.session.get("user_email")
    if not email:
        return None
    col = _col("users")
    if col is None:
        return None
    try:
        return col.find_one({"email": email}, {"password": 0})
    except Exception as e:
        logger.error(f"Fetch user error: {e}")
        return None


def login_required_json(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("user_email"):
            return JsonResponse({"success": False, "error": "Not authenticated"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_redirect(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("user_email"):
            return redirect("/auth/login/")
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── Auth Views ───────────────────────────────────────────────────────────────

@csrf_exempt
def login_view(request):
    """
    GET  → serve login HTML page (sets CSRF cookie)
    POST → JSON login API  (csrf_exempt so fetch() works without token)
    """
    if request.method == "GET":
        if request.session.get("user_email"):
            return redirect("/")
        get_token(request)
        return render(request, "advisory/login.html")

    # POST — authenticate
    try:
        body     = json.loads(request.body)
        email    = body.get("email", "").strip().lower()
        password = body.get("password", "")

        if not email or not password:
            return JsonResponse({"success": False, "error": "Email and password are required."})

        col = _col("users")
        if col is None:
            return JsonResponse({"success": False,
                                 "error": "Database unavailable. Check MongoDB connection in settings."})

        user = col.find_one({"email": email})
        if not user:
            return JsonResponse({"success": False,
                                 "error": "No account found with that email address."})
        if user.get("password") != _hash_password(password):
            return JsonResponse({"success": False,
                                 "error": "Incorrect password. Please try again."})

        try:
            col.update_one({"email": email}, {"$set": {"last_login": datetime.utcnow()}})
        except Exception:
            pass

        request.session["user_email"] = email
        request.session["user_name"]  = user.get("first_name", "Farmer")
        request.session.set_expiry(60 * 60 * 24 * 7)
        request.session.modified = True

        return JsonResponse({"success": True,
                             "name": user.get("first_name", "Farmer"),
                             "email": email})
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON in request body."})
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"})


@csrf_exempt
def register_api(request):
    """POST /auth/register/"""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        body       = json.loads(request.body)
        first_name = body.get("first_name", "").strip()
        last_name  = body.get("last_name", "").strip()
        email      = body.get("email", "").strip().lower()
        password   = body.get("password", "")

        if not all([first_name, email, password]):
            return JsonResponse({"success": False, "error": "First name, email and password are required."})
        if len(password) < 6:
            return JsonResponse({"success": False,
                                 "error": "Password must be at least 6 characters."})
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            return JsonResponse({"success": False,
                                 "error": "Please enter a valid email address."})

        col = _col("users")
        if col is None:
            return JsonResponse({"success": False,
                                 "error": "Database unavailable. Check MongoDB connection."})

        if col.find_one({"email": email}):
            return JsonResponse({"success": False,
                                 "error": "An account with this email already exists. Please sign in."})

        col.insert_one({
            "first_name": first_name,
            "last_name":  last_name,
            "email":      email,
            "password":   _hash_password(password),
            "created_at": datetime.utcnow(),
            "last_login": datetime.utcnow(),
            "is_active":  True,
        })

        request.session["user_email"] = email
        request.session["user_name"]  = first_name
        request.session.set_expiry(60 * 60 * 24 * 7)
        request.session.modified = True

        logger.info(f"New user registered: {email}")
        return JsonResponse({"success": True, "name": first_name, "email": email})

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON in request body."})
    except Exception as e:
        logger.error(f"Register error: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"})


@csrf_exempt
def logout_api(request):
    request.session.flush()
    return JsonResponse({"success": True})


def current_user_api(request):
    email = request.session.get("user_email")
    if not email:
        return JsonResponse({"logged_in": False})
    return JsonResponse({"logged_in": True, "email": email,
                         "name": request.session.get("user_name", "Farmer")})


# ─── Profile ──────────────────────────────────────────────────────────────────

@login_required_redirect
def profile_page(request):
    return render(request, "advisory/profile.html")


@login_required_json
def profile_data_api(request):
    """
    Returns full profile data for the CURRENT logged-in user only.
    Includes per-user analytics using MongoDB aggregation pipelines:

    MongoDB features used:
      1. $facet    — get total / today / week / unique_crops in ONE round-trip
      2. $group    — stress type breakdown (per user)
      3. $group + $project + $substr — hour-of-day usage (peak hours)
      4. $group    — crop distribution (per user)
      5. $group    — language usage (per user)
      6. $bucket   — confidence score distribution (per user)
      7. find()    — recent 10 queries
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({"success": False, "error": "User not found."}, status=404)

    email = user["email"]
    qcol  = _col("farmer_queries")

    # ── Default empty structures ──
    total_queries    = 0
    queries_today    = 0
    queries_week     = 0
    unique_crops     = 0
    stress_breakdown = {}
    recent_queries   = []
    hourly_usage     = []          # NEW: peak-hour data
    crop_distribution = []         # NEW: per-user crop chart
    language_usage    = []         # NEW: language chart
    confidence_dist   = []         # NEW: confidence buckets

    if qcol is not None:
        try:
            now    = datetime.utcnow()
            today  = now.replace(hour=0, minute=0, second=0, microsecond=0)
            wk_ago = now - timedelta(days=7)

            # ──────────────────────────────────────────────────────────────────
            # PIPELINE 1: $facet — summary counts for this user in one shot
            # ──────────────────────────────────────────────────────────────────
            pipeline_summary = [
                {"$match": {"farmer_id": email}},
                {"$facet": {
                    "total":        [{"$count": "n"}],
                    "today":        [{"$match": {"timestamp": {"$gte": today.isoformat()}}},
                                     {"$count": "n"}],
                    "this_week":    [{"$match": {"timestamp": {"$gte": wk_ago.isoformat()}}},
                                     {"$count": "n"}],
                    "unique_crops": [{"$match": {"crop_detected": {"$nin": ["Unknown", "", None]}}},
                                     {"$group": {"_id": "$crop_detected"}},
                                     {"$count": "n"}],
                    "stress_breakdown": [
                        {"$match": {"detected_stress": {"$ne": None}}},
                        {"$group": {"_id": "$detected_stress", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                    ],
                }}
            ]
            r = list(qcol.aggregate(pipeline_summary))
            if r:
                f = r[0]
                total_queries = f["total"][0]["n"]      if f.get("total")        else 0
                queries_today = f["today"][0]["n"]      if f.get("today")        else 0
                queries_week  = f["this_week"][0]["n"]  if f.get("this_week")    else 0
                unique_crops  = f["unique_crops"][0]["n"] if f.get("unique_crops") else 0
                stress_breakdown = {
                    x["_id"]: x["count"]
                    for x in f.get("stress_breakdown", [])
                    if x["_id"]
                }

            # ──────────────────────────────────────────────────────────────────
            # PIPELINE 2: $group + $project + $substr → Peak Hours (0-23)
            # Uses MongoDB $substr to extract "HH" from ISO timestamp string
            # then $toInt to convert to number for sorting
            # ──────────────────────────────────────────────────────────────────
            pipeline_hours = [
                {"$match": {"farmer_id": email, "timestamp": {"$exists": True, "$ne": None}}},
                {"$project": {
                    "hour": {"$toInt": {"$substr": ["$timestamp", 11, 2]}}
                }},
                {"$group": {"_id": "$hour", "count": {"$sum": 1}}},
                {"$sort":  {"_id": 1}},
                {"$project": {"hour": "$_id", "count": 1, "_id": 0}},
            ]
            hourly_raw = list(qcol.aggregate(pipeline_hours))
            # Build a full 24-hour array so the chart has no gaps
            hour_map = {h["hour"]: h["count"] for h in hourly_raw}
            hourly_usage = [{"hour": h, "count": hour_map.get(h, 0)} for h in range(24)]

            # ──────────────────────────────────────────────────────────────────
            # PIPELINE 3: $group → Crop distribution (per user)
            # ──────────────────────────────────────────────────────────────────
            pipeline_crops = [
                {"$match": {"farmer_id": email,
                            "crop_detected": {"$nin": ["Unknown", "", None]}}},
                {"$group": {"_id": "$crop_detected", "count": {"$sum": 1}}},
                {"$sort":  {"count": -1}},
                {"$limit": 8},
                {"$project": {"crop": "$_id", "count": 1, "_id": 0}},
            ]
            crop_distribution = list(qcol.aggregate(pipeline_crops))

            # ──────────────────────────────────────────────────────────────────
            # PIPELINE 4: $group → Language usage (per user)
            # ──────────────────────────────────────────────────────────────────
            pipeline_lang = [
                {"$match":   {"farmer_id": email}},
                {"$group":   {"_id": "$input_language", "count": {"$sum": 1}}},
                {"$sort":    {"count": -1}},
                {"$project": {"language": "$_id", "count": 1, "_id": 0}},
            ]
            language_usage = list(qcol.aggregate(pipeline_lang))

            # ──────────────────────────────────────────────────────────────────
            # PIPELINE 5: $bucket → Confidence score distribution (per user)
            # ──────────────────────────────────────────────────────────────────
            pipeline_conf = [
                {"$match": {"farmer_id": email,
                            "confidence_score": {"$exists": True, "$ne": None}}},
                {"$bucket": {
                    "groupBy":    "$confidence_score",
                    "boundaries": [0, 0.2, 0.4, 0.6, 0.8, 1.01],
                    "default":    "other",
                    "output":     {"count": {"$sum": 1}},
                }},
            ]
            buckets = list(qcol.aggregate(pipeline_conf))
            labels  = ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"]
            for i, b in enumerate(buckets):
                if b["_id"] != "other" and i < len(labels):
                    confidence_dist.append({"range": labels[i], "count": b["count"]})

            # ──────────────────────────────────────────────────────────────────
            # Recent 10 queries — simple find with projection
            # ──────────────────────────────────────────────────────────────────
            recent_queries = list(qcol.find(
                {"farmer_id": email},
                {"_id": 0, "query_text": 1, "original_query": 1,
                 "detected_stress": 1, "crop_detected": 1,
                 "timestamp": 1, "input_language": 1,
                 "confidence_score": 1, "ai_source": 1}
            ).sort("timestamp", -1).limit(20))

            for q in recent_queries:
                if isinstance(q.get("timestamp"), datetime):
                    q["timestamp"] = q["timestamp"].isoformat()

        except Exception as e:
            logger.error(f"Profile analytics error: {e}", exc_info=True)

    def dt_str(v):
        return v.isoformat() if isinstance(v, datetime) else str(v or "")

    return JsonResponse({
        "success": True,
        "user": {
            "first_name": user.get("first_name", ""),
            "last_name":  user.get("last_name",  ""),
            "email":      user.get("email",       ""),
            "created_at": dt_str(user.get("created_at")),
            "last_login": dt_str(user.get("last_login")),
        },
        "stats": {
            "total_queries":     total_queries,
            "queries_today":     queries_today,
            "queries_this_week": queries_week,
            "unique_crops":      unique_crops,
        },
        "stress_breakdown":   stress_breakdown,
        "recent_queries":     recent_queries,
        # ── NEW per-user analytics ──
        "hourly_usage":       hourly_usage,
        "crop_distribution":  crop_distribution,
        "language_usage":     language_usage,
        "confidence_dist":    confidence_dist,
    })


# ─── Analytics page (now just redirects to profile — analytics is IN profile) ──

@login_required_redirect
def analytics_page(request):
    """Analytics tab removed — redirecting to profile which now has full analytics."""
    return redirect("/auth/profile/")


@login_required_json
def analytics_data_api(request):
    """
    Kept for backward compatibility.
    Now returns per-user analytics only (same as profile_data_api).
    """
    return profile_data_api(request)
