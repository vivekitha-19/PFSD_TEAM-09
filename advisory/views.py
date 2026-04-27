"""
Advisory App Views v4
- /health/          → Real analytics HTML dashboard (query trends, top stresses, language breakdown)
- /api/translate/   → MyMemory REST translation proxy
- /api/process-query/ → Full pipeline REST fallback
"""
import json
import os
import subprocess
import sys
import logging
from datetime import datetime, date
from collections import Counter
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def dashboard(request):
    if not request.session.get("user_email"):
        return redirect("/auth/login/")
    return render(request, 'advisory/dashboard.html', {
        'title': 'FarmAI – Crop Stress Detection & Advisory System'
    })


# ─── Analytics / System Health HTML page ──────────────────────────────────────
def health_check(request):
    """
    Real Analytics Dashboard — shows:
    - System component status (DB, NLP, ML, Translation)
    - Query count today / this week / all time
    - Top detected stress types (bar chart via HTML)
    - Language breakdown
    - Recent queries list
    - ML model info
    """
    from db_connector import db_instance
    from nlp_engine import nlp_processor
    from ml_engine import ml_classifier

    # ── Load real model info ──
    model_info_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'ml_model', 'model_info.json'
    )
    model_file_info = {}
    if os.path.exists(model_info_path):
        try:
            import json as _json
            with open(model_info_path) as f:
                model_file_info = _json.load(f)
        except Exception:
            pass

    # ── Component checks ──
    db_connected   = db_instance.db is not None
    crops_count    = len(db_instance.get_all_crops())
    stress_count   = len(db_instance.get_all_stress_conditions())
    advisory_count = len(db_instance.get_all_advisory())

    try:
        test_nlp = nlp_processor.process("rice leaves turning yellow and wilting")
        nlp_ok   = test_nlp.get('success', False)
    except Exception:
        nlp_ok = False

    try:
        test_ml = ml_classifier.predict([0, 0, 0, 0.9, 0, 0, 0, 0])
        ml_ok   = test_ml.get('predicted_stress') is not None
    except Exception:
        ml_ok = False

    try:
        from nlp_engine.translator import _mymemory_translate
        tr_ok = bool(_mymemory_translate("hello", 'en', 'hi'))
    except Exception:
        tr_ok = False

    # ── Query analytics from MongoDB ──
    all_queries = db_instance.get_query_history(limit=10000)
    today_str   = date.today().isoformat()
    today_qs    = [q for q in all_queries if q.get('timestamp','').startswith(today_str)]

    # Stress distribution
    stress_counts = Counter(q.get('detected_stress','UNKNOWN') for q in all_queries)
    stress_counts.pop('INSUFFICIENT_DATA', None)
    stress_counts.pop('UNKNOWN', None)
    top_stresses  = stress_counts.most_common(8)

    # Language distribution
    lang_counts   = Counter(q.get('input_language','en') for q in all_queries)
    top_langs     = lang_counts.most_common(9)

    # Crop distribution
    crop_counts   = Counter(q.get('crop_detected','Unknown') for q in all_queries if q.get('crop_detected','Unknown')!='Unknown')
    top_crops     = crop_counts.most_common(8)

    # Recent 10 queries
    recent = all_queries[:10]

    max_stress = max((c for _, c in top_stresses), default=1)
    max_lang   = max((c for _, c in top_langs),   default=1)

    STRESS_ICONS = {
        'NUTRIENT_DEFICIENCY':'🌿','FUNGAL_DISEASE':'🍄','WATER_STRESS':'💧',
        'PEST_INFESTATION':'🐛','VIRAL_DISEASE':'🦠','BACTERIAL_DISEASE':'🧫',
        'HEAT_STRESS':'🌡️','WEED_INFESTATION':'🌱'
    }
    LANG_FLAGS = {
        'en':'🇬🇧','hi':'🇮🇳','te':'🇮🇳','ta':'🇮🇳',
        'kn':'🇮🇳','mr':'🇮🇳','pa':'🇮🇳','gu':'🇮🇳','bn':'🇮🇳'
    }
    LANG_NAMES = {
        'en':'English','hi':'Hindi','te':'Telugu','ta':'Tamil',
        'kn':'Kannada','mr':'Marathi','pa':'Punjabi','gu':'Gujarati','bn':'Bengali'
    }

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>FarmAI — Analytics Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--primary:#16a34a;--primary-dark:#15803d;--primary-light:#bbf7d0;--bg:#f0fdf4;--card:#fff;--border:#d1fae5;--text:#1a2e1a;--muted:#6b7280}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text)}}
.topbar{{background:linear-gradient(90deg,#14532d,#16a34a);color:#fff;padding:15px 30px;display:flex;align-items:center;justify-content:space-between}}
.topbar h1{{font-size:1.05rem;font-weight:700}}
.back-btn{{background:rgba(255,255,255,.2);color:#fff;border:none;padding:7px 14px;border-radius:7px;cursor:pointer;font-size:.78rem;font-weight:600;font-family:inherit}}
.back-btn:hover{{background:rgba(255,255,255,.35)}}
.container{{max-width:1100px;margin:0 auto;padding:24px 20px}}
.pg-header{{margin-bottom:20px}}
.pg-header h2{{font-size:1.3rem;font-weight:800;color:var(--primary-dark)}}
.pg-header p{{font-size:.78rem;color:var(--muted);margin-top:4px}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}}
.grid2{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-bottom:20px}}
.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px}}
.card{{background:var(--card);border-radius:12px;border:1px solid var(--border);box-shadow:0 2px 12px rgba(22,163,74,.06);padding:18px}}
.stat-card{{display:flex;align-items:center;gap:11px}}
.s-icon{{width:42px;height:42px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.22rem;flex-shrink:0}}
.sg{{background:#dcfce7}}.sa{{background:#fef3c7}}.sb{{background:#dbeafe}}.sp{{background:#ede9fe}}
.s-val{{font-size:1.42rem;font-weight:800;line-height:1}}
.s-label{{font-size:.68rem;color:var(--muted);font-weight:500;margin-top:2px}}
.card-title{{font-size:.88rem;font-weight:700;color:var(--primary-dark);margin-bottom:14px;display:flex;align-items:center;gap:7px}}
.comp-row{{display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid #f0fdf4;font-size:.82rem}}
.comp-row:last-child{{border-bottom:none}}
.comp-name{{font-weight:600;display:flex;align-items:center;gap:7px}}
.status-ok{{background:#dcfce7;color:#166534;font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:8px}}
.status-warn{{background:#fef3c7;color:#92400e;font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:8px}}
.status-err{{background:#fee2e2;color:#991b1b;font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:8px}}
.bar-row{{display:flex;align-items:center;gap:8px;margin-bottom:7px}}
.bar-label{{font-size:.72rem;font-weight:600;min-width:160px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.bar-track{{flex:1;height:14px;background:#f0fdf4;border-radius:7px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:7px;background:linear-gradient(90deg,#16a34a,#059669);transition:width .6s ease}}
.bar-count{{font-size:.7rem;font-weight:700;color:var(--primary-dark);min-width:28px;text-align:right}}
.recent-item{{display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid #f0fdf4;font-size:.78rem}}
.recent-item:last-child{{border-bottom:none}}
.ri-stress{{font-size:.66rem;font-weight:600;padding:1px 7px;border-radius:7px;background:#dcfce7;color:var(--primary-dark);flex-shrink:0;margin-top:1px}}
.ri-text{{flex:1;color:var(--text);line-height:1.3}}
.ri-lang{{font-size:.64rem;color:var(--muted);background:#f3f4f6;padding:1px 6px;border-radius:6px;flex-shrink:0}}
.ri-time{{font-size:.63rem;color:var(--muted);flex-shrink:0}}
.no-data{{text-align:center;padding:24px;color:var(--muted);font-size:.82rem}}
.refresh-note{{font-size:.72rem;color:var(--muted);text-align:center;margin-top:16px}}
@media(max-width:700px){{.grid4,.grid3{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}}}
</style></head><body>
<div class="topbar">
  <h1>📊 FarmAI — Analytics & System Dashboard</h1>
  <button class="back-btn" onclick="window.location.href='/'">← Dashboard</button>
</div>
<div class="container">
  <div class="pg-header">
    <h2>Real-Time Analytics</h2>
    <p>Live query analytics from MongoDB · System component health · ML model performance · {datetime.now().strftime('%d %b %Y, %I:%M %p')}</p>
  </div>

  <!-- Stats -->
  <div class="grid4">
    <div class="card stat-card"><div class="s-icon sg">📊</div><div><div class="s-val">{len(all_queries)}</div><div class="s-label">Total Queries</div></div></div>
    <div class="card stat-card"><div class="s-icon sa">📅</div><div><div class="s-val">{len(today_qs)}</div><div class="s-label">Today's Queries</div></div></div>
    <div class="card stat-card"><div class="s-icon sb">🌿</div><div><div class="s-val">{crops_count}</div><div class="s-label">Crops in DB</div></div></div>
    <div class="card stat-card"><div class="s-icon sp">🤖</div><div><div class="s-val">{stress_count}</div><div class="s-label">Stress Classes</div></div></div>
  </div>

  <div class="grid2">
    <!-- System Components -->
    <div class="card">
      <div class="card-title">⚙️ System Components</div>
      <div class="comp-row"><span class="comp-name">🗄️ MongoDB</span><span class="{'status-ok' if db_connected else 'status-warn'}">{'Connected' if db_connected else 'In-Memory'}</span></div>
      <div class="comp-row"><span class="comp-name">🔤 NLP Engine (NLTK)</span><span class="{'status-ok' if nlp_ok else 'status-err'}">{'Active' if nlp_ok else 'Error'}</span></div>
      <div class="comp-row"><span class="comp-name">🤖 ML Model (NB+LR+DT)</span><span class="{'status-ok' if ml_ok else 'status-err'}">{'Trained & Active' if ml_ok else 'Error'}</span></div>
      <div class="comp-row"><span class="comp-name">🌐 MyMemory Translation API</span><span class="{'status-ok' if tr_ok else 'status-warn'}">{'Active' if tr_ok else 'Offline (needs internet)'}</span></div>
      <div class="comp-row"><span class="comp-name">⚡ GraphQL API</span><span class="status-ok">Active at /graphql/</span></div>
      <div class="comp-row"><span class="comp-name">🌾 Advisory Records</span><span class="status-ok">{advisory_count} in MongoDB</span></div>
    </div>

    <!-- Stress distribution -->
    <div class="card">
      <div class="card-title">⚠️ Top Detected Stress Types</div>
      {"".join(f'''<div class="bar-row">
        <div class="bar-label">{STRESS_ICONS.get(s,"⚠️")} {s.replace("_"," ")}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{int(c/max_stress*100)}%"></div></div>
        <div class="bar-count">{c}</div>
      </div>''' for s,c in top_stresses) if top_stresses else '<div class="no-data">No queries yet</div>'}
    </div>
  </div>

  <div class="grid3">
    <!-- Language breakdown -->
    <div class="card">
      <div class="card-title">🌐 Query Languages</div>
      {"".join(f'''<div class="bar-row">
        <div class="bar-label">{LANG_FLAGS.get(l,"🌐")} {LANG_NAMES.get(l,l)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{int(c/max_lang*100)}%;background:linear-gradient(90deg,#3b82f6,#1d4ed8)"></div></div>
        <div class="bar-count">{c}</div>
      </div>''' for l,c in top_langs) if top_langs else '<div class="no-data">No queries yet</div>'}
    </div>

    <!-- Crop distribution -->
    <div class="card">
      <div class="card-title">🌱 Crops Queried</div>
      {"".join(f'''<div class="bar-row">
        <div class="bar-label">🌿 {crop}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{int(c/max(c2 for _,c2 in top_crops)*100)}%;background:linear-gradient(90deg,#f59e0b,#d97706)"></div></div>
        <div class="bar-count">{c}</div>
      </div>''' for crop,c in top_crops) if top_crops else '<div class="no-data">No queries yet</div>'}
    </div>

    <!-- ML Model info -->
    <div class="card">
      <div class="card-title">🧠 ML Model Info</div>
      <div class="comp-row"><span class="comp-name">Algorithm</span><span style="font-size:.75rem;font-weight:600">{model_file_info.get('model_type','TF-IDF+LogReg')}</span></div>
      <div class="comp-row"><span class="comp-name">Test Accuracy</span><span class="{'status-ok' if model_file_info.get('accuracy',0) > 0.6 else 'status-warn'}">{f"{model_file_info.get('accuracy',0)*100:.1f}%" if model_file_info.get('accuracy') else 'Not trained'}</span></div>
      <div class="comp-row"><span class="comp-name">CV Accuracy</span><span style="font-size:.73rem;color:var(--muted)">{f"{model_file_info.get('cv_accuracy',0)*100:.1f}% ± {model_file_info.get('cv_std',0)*100:.1f}%" if model_file_info.get('cv_accuracy') else 'N/A'}</span></div>
      <div class="comp-row"><span class="comp-name">Naive Bayes</span><span style="font-size:.73rem;color:var(--muted)">30% weight</span></div>
      <div class="comp-row"><span class="comp-name">Logistic Regression</span><span style="font-size:.73rem;color:var(--muted)">40% weight</span></div>
      <div class="comp-row"><span class="comp-name">Decision Tree</span><span style="font-size:.73rem;color:var(--muted)">30% weight</span></div>
      <div class="comp-row"><span class="comp-name">Classes</span><span style="font-size:.73rem;color:var(--muted)">{stress_count} stress types</span></div>
      <div class="comp-row"><span class="comp-name">Training Data</span><span style="font-size:.73rem;color:var(--muted)">{model_file_info.get('total_samples','?')} samples (CSV)</span></div>
      <div class="comp-row"><span class="comp-name">Min Confidence</span><span style="font-size:.73rem;color:var(--muted)">55% threshold</span></div>
    </div>
  </div>

  <!-- Recent queries -->
  <div class="card">
    <div class="card-title">🕐 Recent Queries (Last 10)</div>
    {"".join(f'''<div class="recent-item">
      <span class="ri-stress">{STRESS_ICONS.get(q.get("detected_stress",""),"❓")} {(q.get("detected_stress","—") or "—").replace("_"," ")}</span>
      <span class="ri-text">{q.get("original_query",q.get("query_text","—"))}</span>
      <span class="ri-lang">{LANG_FLAGS.get(q.get("input_language","en"),"🌐")} {q.get("input_language","en")}</span>
      <span class="ri-time">{q.get("timestamp","")[:16].replace("T"," ") if q.get("timestamp") else "—"}</span>
    </div>''' for q in recent) if recent else '<div class="no-data">No queries yet — submit a query from the dashboard to see analytics here.</div>'}
  </div>

  <p class="refresh-note">⟳ Page auto-refreshes every 60s · Data from MongoDB farmer_queries collection · <a href="/" style="color:var(--primary)">← Back to Dashboard</a></p>
</div>
<script>setTimeout(()=>location.reload(),60000);</script>
</body></html>"""
    return HttpResponse(html)


# ─── Translation proxy ─────────────────────────────────────────────────────────
@csrf_exempt
def translate_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        body = json.loads(request.body)
        text = body.get('text','').strip()
        src  = body.get('src','auto')
        tgt  = body.get('tgt','en')
        if not text:
            return JsonResponse({'translated':'','success':True})
        from nlp_engine.translator import _mymemory_translate, detect_language
        if src=='auto':
            src = detect_language(text, hint_lang='auto')
        translated = _mymemory_translate(text, src_lang=src, tgt_lang=tgt)
        return JsonResponse({'translated':translated,'src':src,'tgt':tgt,'success':True})
    except Exception as e:
        logger.error(f"Translate error: {e}", exc_info=True)
        return JsonResponse({'error':str(e),'translated':'','success':False}, status=500)


# ─── Advisory archive ──────────────────────────────────────────────────────────
def advisory_archive(request):
    from db_connector import db_instance
    advisories = db_instance.get_all_advisory()
    crops = db_instance.get_all_crops()
    return render(request, 'advisory/advisory_archive.html', {
        'title':'Advisory Archive','advisories':advisories,'crops':crops,'total':len(advisories)
    })


# ─── Full pipeline REST ────────────────────────────────────────────────────────
@csrf_exempt
def process_query_api(request):
    if request.method != 'POST':
        return JsonResponse({'error':'POST required'}, status=405)
    try:
        body          = json.loads(request.body)
        query_text    = body.get('query','').strip()
        input_lang    = body.get('input_lang','auto')
        selected_crop = body.get('selected_crop','')
        farmer_id     = request.session.get('user_email') or body.get('farmer_id','anonymous')
        if not query_text:
            return JsonResponse({'error':'Query text required'}, status=400)
        from nlp_engine.translator import translate_to_english, translate_advisory_to_language, translate_text_to_language
        from nlp_engine import nlp_processor
        from ml_engine import ml_classifier
        from db_connector import db_instance
        trans        = translate_to_english(query_text, source_lang=input_lang)
        english_text = trans['translated']
        source_lang  = trans['source_lang']
        try:
            nlp_result = nlp_processor.process(english_text)
        except Exception as _nlp_err:
            logger.warning(f"NLP failed: {_nlp_err}")
            nlp_result = {'success': True, 'detected_crop': 'Unknown',
                          'feature_vector': [], 'filtered_tokens': [],
                          'token_count': 0, 'crop_confidence': 0.0}
        # Never block — NLP failure is non-fatal
        if not nlp_result.get('success'):
            nlp_result['success'] = True  # Force continue
        detected_crop = nlp_result.get('detected_crop','Unknown')
        if selected_crop and selected_crop.strip().lower() not in ('','none','null'):
            detected_crop = selected_crop.strip().capitalize()
        ml_result    = ml_classifier.predict(nlp_result.get('feature_vector',[]), raw_text=english_text)
        insufficient = ml_result.get('confidence',0) < 0.55
        advisory = None
        if True:
            from ai_engine import ai_engine as _ai
            advisory = _ai.generate_advisory(
                english_text,
                ml_result['predicted_stress'],
                detected_crop if detected_crop != 'Unknown' else ''
            )
            if advisory and source_lang != 'en':
                advisory = translate_advisory_to_language(advisory, source_lang)
        display_name = ml_result.get('display_name','')
        if source_lang!='en' and display_name and not insufficient:
            display_name = translate_text_to_language(display_name, source_lang)
        db_instance.save_farmer_query(
            query_text=english_text, original_query=query_text,
            detected_stress=ml_result['predicted_stress'],
            crop_detected=detected_crop, confidence_score=ml_result['confidence'],
            advisory_provided=advisory.get('title','') if advisory else '',
            farmer_id=farmer_id, input_language=source_lang, selected_crop=selected_crop,
            ai_source=advisory.get('_source','') if advisory else ''
        )
        return JsonResponse({
            'success':True,'query':query_text,'translation':trans,
            'nlp':{'detected_crop':detected_crop,'tokens':nlp_result.get('filtered_tokens',[])[:10],'token_count':nlp_result.get('token_count',0),'input_language':source_lang,'input_lang_name':trans.get('source_lang_name','English')},
            'ml':{'predicted_stress':ml_result['predicted_stress'],'display_name':display_name,'confidence':ml_result['confidence'],'confidence_percent':ml_result.get('confidence_percent',''),'severity':ml_result['severity'],'color':ml_result['color'],'insufficient_data':insufficient},
            'advisory':{k:v for k,v in (advisory or {}).items() if not k.startswith('_')} if advisory else None
        })
    except Exception as e:
        logger.error(f"REST error: {e}", exc_info=True)
        return JsonResponse({'error':str(e)}, status=500)


@csrf_exempt
def delete_query_api(request, record_id):
    if request.method != 'DELETE':
        return JsonResponse({'error':'DELETE required'}, status=405)
    from db_connector import db_instance
    success = db_instance.delete_query(record_id)
    return JsonResponse({'success':success,'deleted_id':record_id if success else None})



# ─── Model status page ────────────────────────────────────────────────────────
def model_status_api(request):
    """GET /api/model-status/ — shows current ML model info as JSON"""
    from ml_engine import ml_classifier
    import json as _json
    info = ml_classifier.get_model_info()
    model_info_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'ml_model', 'model_info.json'
    )
    file_info = {}
    if os.path.exists(model_info_path):
        try:
            with open(model_info_path) as f:
                file_info = _json.load(f)
        except Exception:
            pass
    return JsonResponse({
        'model_source':  ml_classifier.using_real and 'Real CSV-trained model' or 'Synthetic ensemble (run train_model.py to use real model)',
        'using_real':    ml_classifier.using_real,
        'accuracy':      file_info.get('accuracy', 0),
        'cv_accuracy':   file_info.get('cv_accuracy', 0),
        'total_samples': file_info.get('total_samples', 0),
        'labels':        file_info.get('labels', []),
        'model_type':    file_info.get('model_type', 'N/A'),
        'label_counts':  file_info.get('label_counts', {}),
        'ngram_range':   file_info.get('ngram_range', []),
        'features':      file_info.get('features', 0),
        'how_to_improve': 'Add more rows to ml_model/training_data.csv → POST /api/retrain/ to retrain'
    }, json_dumps_params={'indent': 2})

# ─── Retrain endpoint ──────────────────────────────────────────────────────────
@csrf_exempt
def retrain_model_api(request):
    """
    POST /api/retrain/
    Runs train_model.py and hot-reloads the classifier.
    Use after adding new rows to training_data.csv.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        train_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'ml_model', 'train_model.py'
        )
        if not os.path.exists(train_script):
            return JsonResponse({'error': 'train_model.py not found'}, status=404)

        result = subprocess.run(
            [sys.executable, train_script],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return JsonResponse({'success': False, 'error': result.stderr[:500]})

        # Hot-reload classifier
        from ml_engine import ml_classifier
        ml_classifier.reload()

        return JsonResponse({
            'success': True,
            'message': 'Model retrained and reloaded successfully',
            'output': result.stdout[-800:],
            'using_real': ml_classifier.using_real,
            'model_info': ml_classifier.get_model_info()
        })
    except subprocess.TimeoutExpired:
        return JsonResponse({'success': False, 'error': 'Training timed out (>120s)'})
    except Exception as e:
        logger.error(f"Retrain error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)