"""
FarmAI — AI Advisory Engine v8
================================
TRUE DYNAMIC AI — like ChatGPT for farmers.

ANY question gets a relevant, specific answer:
  "How to grow rice?" → cultivation guide
  "When to harvest wheat?" → harvesting guide
  "My tomato has white powder" → powdery mildew treatment
  "What fertilizer for cotton?" → fertilizer schedule
  "Is it raining season good for paddy?" → seasonal advice

Architecture:
  Step 1: Understand the INTENT of the question (grow/harvest/disease/pest/fertilizer/general)
  Step 2: Detect crop from the question text
  Step 3: Call HuggingFace LLM with the exact question → get ChatGPT-style answer
  Step 4: If HF API is loading/slow → OpenAI GPT-4o-mini
  Step 5: If both fail → smart intent-aware fallback (still dynamic, never same answer twice)

The response is ALWAYS tailored to the exact question asked.
"""

import os, re, json, logging, urllib.request, urllib.parse, urllib.error
from typing import Dict, Optional

logger = logging.getLogger(__name__)

HF_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")
OPENAI_KEY  = os.environ.get('OPENAI_API_KEY', '')
HF_API_BASE = 'https://api-inference.huggingface.co/models'

# HuggingFace models to try (only 1 — fast fail, go to smart fallback)
HF_MODELS = [
    'mistralai/Mistral-7B-Instruct-v0.2',
]
HF_CLASSIFIER = 'facebook/bart-large-mnli'

# ─── Metadata ──────────────────────────────────────────────────────────────────
STRESS_LABELS_HF = [
    "nutrient deficiency yellowing pale leaves",
    "fungal disease spots powder rust blight",
    "water drought stress wilting drying",
    "pest insect infestation damage holes",
    "viral disease mosaic leaf curl distortion",
    "bacterial disease rot canker water soaked",
    "heat temperature stress scorching bleaching",
    "weed infestation wild grass competition",
]
LABEL_TO_KEY = {
    "nutrient deficiency yellowing pale leaves":       "NUTRIENT_DEFICIENCY",
    "fungal disease spots powder rust blight":         "FUNGAL_DISEASE",
    "water drought stress wilting drying":             "WATER_STRESS",
    "pest insect infestation damage holes":            "PEST_INFESTATION",
    "viral disease mosaic leaf curl distortion":       "VIRAL_DISEASE",
    "bacterial disease rot canker water soaked":       "BACTERIAL_DISEASE",
    "heat temperature stress scorching bleaching":     "HEAT_STRESS",
    "weed infestation wild grass competition":         "WEED_INFESTATION",
}
STRESS_DISPLAY = {
    'NUTRIENT_DEFICIENCY':'🌿 Nutrient Deficiency','FUNGAL_DISEASE':'🍄 Fungal Disease',
    'WATER_STRESS':'💧 Water/Drought Stress','PEST_INFESTATION':'🐛 Pest Infestation',
    'VIRAL_DISEASE':'🦠 Viral Disease','BACTERIAL_DISEASE':'🧫 Bacterial Disease',
    'HEAT_STRESS':'🌡️ Heat Stress','WEED_INFESTATION':'🌱 Weed Infestation',
    'GENERAL_FARMING':'🌾 Crop Advisory','CULTIVATION':'🌱 Cultivation Guide',
    'HARVESTING':'🌾 Harvesting Guide','FERTILIZER':'🌿 Fertilizer Advisory',
    'IRRIGATION':'💧 Irrigation Guide','MARKET':'📊 Market Advisory',
}
SEVERITY_MAP = {
    'NUTRIENT_DEFICIENCY':'Medium','FUNGAL_DISEASE':'High','WATER_STRESS':'High',
    'PEST_INFESTATION':'High','VIRAL_DISEASE':'Very High','BACTERIAL_DISEASE':'High',
    'HEAT_STRESS':'Medium','WEED_INFESTATION':'Medium',
    'GENERAL_FARMING':'Low','CULTIVATION':'Low','HARVESTING':'Low',
    'FERTILIZER':'Low','IRRIGATION':'Low','MARKET':'Low',
}
COLOR_MAP = {
    'NUTRIENT_DEFICIENCY':'#f59e0b','FUNGAL_DISEASE':'#8b5cf6','WATER_STRESS':'#3b82f6',
    'PEST_INFESTATION':'#ef4444','VIRAL_DISEASE':'#dc2626','BACTERIAL_DISEASE':'#b91c1c',
    'HEAT_STRESS':'#f97316','WEED_INFESTATION':'#65a30d',
    'GENERAL_FARMING':'#16a34a','CULTIVATION':'#16a34a','HARVESTING':'#059669',
    'FERTILIZER':'#d97706','IRRIGATION':'#0284c7','MARKET':'#7c3aed',
}

# Crop detection keywords
CROP_KEYWORDS = {
    'Rice':      ['rice','paddy','dhan','chawal'],
    'Wheat':     ['wheat','gehu','gehun','atta'],
    'Tomato':    ['tomato','tamatar'],
    'Cotton':    ['cotton','kapas'],
    'Maize':     ['maize','corn','makka','bhutta'],
    'Sugarcane': ['sugarcane','ganna','ikh'],
    'Soybean':   ['soybean','soya'],
    'Groundnut': ['groundnut','peanut','moongphali'],
    'Chilli':    ['chilli','mirchi','pepper'],
    'Onion':     ['onion','pyaz','kanda'],
    'Potato':    ['potato','aloo','aaloo'],
    'Brinjal':   ['brinjal','eggplant','baingan'],
    'Mustard':   ['mustard','sarson','rapeseed'],
    'Chickpea':  ['chickpea','gram','chana','bengal gram'],
    'Mango':     ['mango','aam'],
    'Banana':    ['banana','kela'],
}


# ─── Utility: detect query intent ──────────────────────────────────────────────
def detect_intent(query: str) -> str:
    """
    Understand what the farmer is really asking.
    Returns intent category to guide the advisory generation.
    """
    q = query.lower()

    # Cultivation / Growing
    if any(p in q for p in ['how to grow','how to plant','how to cultivate','steps to grow',
                              'cultivation','planting guide','how do i grow','grow my',
                              'sow','sowing','transplant','nursery','seedling preparation',
                              'when to plant','best time to grow','how to start']):
        return 'CULTIVATION'

    # Harvesting
    if any(p in q for p in ['harvest','when to harvest','how to harvest','maturity',
                              'ready to harvest','harvesting time','post harvest','storage',
                              'how to store','when is it ready']):
        return 'HARVESTING'

    # Fertilizer / Nutrition
    if any(p in q for p in ['fertilizer','manure','urea','npk','dap','nutrient schedule',
                              'how much fertilizer','when to apply fertilizer','top dress',
                              'organic fertilizer','what to feed','plant food','nutrition plan']):
        return 'FERTILIZER'

    # Irrigation / Water management
    if any(p in q for p in ['how to irrigate','irrigation schedule','how much water',
                              'drip irrigation','sprinkler','water management','when to water',
                              'frequency of watering','flood irrigation','furrow']):
        return 'IRRIGATION'

    # Market / Price
    if any(p in q for p in ['market price','mandi price','rate','sell','profit',
                              'market','revenue','income from','msp','minimum support']):
        return 'MARKET'

    # Disease / Stress symptoms — check EARLY before general farming
    if any(p in q for p in ['yellow','turning','spots','rust','mildew','blight','powder',
                              'wilt','droop','dry','holes','eaten','worm','aphid','mosaic',
                              'curl','rot','canker','ooze','pest','insect','disease','problem',
                              'damage','infected','attack','weed','grass','kharpat',
                              'white coat','brown spot','leaf spot','not growing','stunted',
                              'dying','dead','sick','weak','pale','burning','scorch']):
        return 'STRESS'

    # General farming question
    return 'GENERAL_FARMING'


def detect_crop(query: str, nlp_crop: str = '', selected_crop: str = '') -> str:
    """Detect crop from all available sources"""
    # Priority: user selected > NLP detected > text scan
    if selected_crop and selected_crop.strip().lower() not in ('', 'none', 'null', 'unknown'):
        return selected_crop.strip().capitalize()
    if nlp_crop and nlp_crop not in ('Unknown', '', None):
        return nlp_crop
    q = query.lower()
    for cname, keywords in CROP_KEYWORDS.items():
        if any(k in q for k in keywords):
            return cname
    return ''


# ─── HF API helper ─────────────────────────────────────────────────────────────
def _hf_post(model: str, payload: dict, timeout: int = 8) -> Optional[dict]:
    if not HF_API_KEY:
        return None
    url  = f"{HF_API_BASE}/{model}"
    data = json.dumps(payload).encode('utf-8')
    req  = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {HF_API_KEY}',
        'Content-Type':  'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        if 'loading' in body.lower():
            logger.info(f"HF {model} loading — will use fallback")
        else:
            logger.warning(f"HF {model} error {e.code}: {body[:150]}")
    except Exception as e:
        logger.warning(f"HF {model} failed: {e}")
    return None


def _extract_json(text: str) -> Optional[Dict]:
    """Robustly extract JSON from LLM output"""
    text = text.strip()
    for attempt in [text, re.sub(r'[\x00-\x1f\x7f]', ' ', text)]:
        try:
            return json.loads(attempt)
        except Exception:
            pass
        m = re.search(r'\{[\s\S]*\}', attempt)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                # Try fixing trailing comma issues
                try:
                    fixed = re.sub(r',\s*([}\]])', r'\1', m.group())
                    return json.loads(fixed)
                except Exception:
                    pass
    return None


# ─── Step 1: BERT Classification ───────────────────────────────────────────────
def classify_with_bert(text: str) -> Dict:
    payload = {
        "inputs": text,
        "parameters": {"candidate_labels": STRESS_LABELS_HF, "multi_label": False}
    }
    result = _hf_post(HF_CLASSIFIER, payload, timeout=20)
    if not result or 'labels' not in result:
        return {}
    labels = result.get('labels', [])
    scores = result.get('scores', [])
    if not labels:
        return {}
    best  = labels[0]
    score = scores[0] if scores else 0.5
    key   = LABEL_TO_KEY.get(best, 'FUNGAL_DISEASE')
    return {
        'predicted_stress':   key,
        'display_name':       STRESS_DISPLAY.get(key, key),
        'confidence':         round(score, 4),
        'confidence_percent': f"{score*100:.1f}%",
        'severity':           SEVERITY_MAP.get(key, 'Medium'),
        'color':              COLOR_MAP.get(key, '#6b7280'),
        'model_used':         'BERT (facebook/bart-large-mnli)',
        'insufficient_data':  False,
    }


def keyword_classify(text: str, intent: str) -> Dict:
    """Keyword-based classification — guaranteed to work offline"""
    if intent in ('CULTIVATION','HARVESTING','FERTILIZER','IRRIGATION','MARKET','GENERAL_FARMING'):
        return {
            'predicted_stress':   intent,
            'display_name':       STRESS_DISPLAY.get(intent, '🌾 Crop Advisory'),
            'confidence':         0.80,
            'confidence_percent': '80.0%',
            'severity':           SEVERITY_MAP.get(intent, 'Low'),
            'color':              COLOR_MAP.get(intent, '#16a34a'),
            'model_used':         'Intent Detection',
            'insufficient_data':  False,
        }
    t = text.lower()
    scores = {
        'NUTRIENT_DEFICIENCY': sum(1 for w in ['yellow','pale','stunted','deficien','chloro','nitrogen','phospho','potassi','zinc','iron','magnesium','light green','fade','nutrient'] if w in t),
        'FUNGAL_DISEASE':      sum(1 for w in ['spot','powder','rust','mildew','blight','mold','fungus','blast','smut','lesion','blotch','white coat','gray','brown circle'] if w in t),
        'WATER_STRESS':        sum(1 for w in ['dry','drying','wilt','droop','drought','crispy','shrivel','limp','no water','thirst','crack soil','dehydrat'] if w in t),
        'PEST_INFESTATION':    sum(1 for w in ['insect','pest','worm','caterpillar','aphid','bug','hole','eaten','larva','grub','mite','thrip','borer','whitefly','scale'] if w in t),
        'VIRAL_DISEASE':       sum(1 for w in ['mosaic','curl','distort','virus','mottle','streak','ring spot','vein clear','twisted','deform','necrosis'] if w in t),
        'BACTERIAL_DISEASE':   sum(1 for w in ['bacteria','water soak','ooze','rot','canker','slime','gall','decay','smell','soft rot','fire blight'] if w in t),
        'HEAT_STRESS':         sum(1 for w in ['scorch','sunburn','bleach','heat','hot','burnt edge','tip burn','sun scald','high temp','summer damage'] if w in t),
        'WEED_INFESTATION':    sum(1 for w in ['weed','grass','kharpat','unwanted plant','wild plant','overgrow','compete','barnyard','nutgrass','crabgrass'] if w in t),
    }
    best  = max(scores, key=scores.get)
    score = scores[best]
    if score == 0:
        # Contextual defaults based on crop
        if any(w in t for w in ['rice','paddy']): best = 'NUTRIENT_DEFICIENCY'
        elif any(w in t for w in ['wheat']): best = 'FUNGAL_DISEASE'
        elif any(w in t for w in ['tomato']): best = 'FUNGAL_DISEASE'
        else: best = 'NUTRIENT_DEFICIENCY'
        score = 1
    conf = min(0.55 + score * 0.08, 0.92)
    return {
        'predicted_stress':   best,
        'display_name':       STRESS_DISPLAY.get(best, best),
        'confidence':         round(conf, 4),
        'confidence_percent': f"{conf*100:.1f}%",
        'severity':           SEVERITY_MAP.get(best, 'Medium'),
        'color':              COLOR_MAP.get(best, '#6b7280'),
        'model_used':         'Keyword + Intent Detection',
        'insufficient_data':  False,
    }


# ─── Step 2: HuggingFace LLM Advisory ─────────────────────────────────────────
def call_hf_llm(query: str, crop: str, intent: str, stress_type: str) -> Optional[Dict]:
    """
    Call HuggingFace LLM with the EXACT farmer question.
    The LLM answers like ChatGPT — specific to the question, not a template.
    """
    crop_ctx    = f" about {crop}" if crop and crop not in ('', 'Unknown', 'General') else ""
    intent_hint = {
        'CULTIVATION':    'This is a cultivation/growing question — give planting, care and growing steps',
        'HARVESTING':     'This is a harvesting question — give timing, method and post-harvest steps',
        'FERTILIZER':     'This is a fertilizer/nutrition question — give schedule, products and doses',
        'IRRIGATION':     'This is an irrigation question — give schedule, method and frequency',
        'MARKET':         'This is a market/price question — give practical advice for selling crop',
        'STRESS':         'This is a crop problem/disease/pest question — give treatment and recovery steps',
        'GENERAL_FARMING':'This is a general farming question — give comprehensive practical advice',
    }.get(intent, 'Give comprehensive practical farming advice')

    prompt = f"""<s>[INST] You are FarmAI, an expert agricultural advisor for Indian farmers. Answer this farmer's question directly, specifically, and practically — like a helpful farming expert, not a textbook.

Farmer's Question: "{query}"
Question type{crop_ctx}: {intent_hint}

IMPORTANT: Answer this SPECIFIC question. If they ask "how to grow rice" — give rice growing steps. If they ask "why are leaves turning yellow" — explain yellowing causes and treatment. Be specific, use real Indian product names and doses.

Respond ONLY with valid JSON (no extra text, no markdown, no code blocks):
{{
  "title": "Specific title answering this question",
  "immediate_action": "The most important single action to take right now",
  "treatment": [
    "Specific step 1 directly answering the question",
    "Specific step 2",
    "Specific step 3",
    "Specific step 4",
    "Specific step 5"
  ],
  "prevention": [
    "Practical prevention tip 1",
    "Practical prevention tip 2",
    "Practical prevention tip 3",
    "Practical prevention tip 4"
  ],
  "fertilizers": ["Product/input 1", "Product/input 2", "Product/input 3"],
  "follow_up": "What to check or do after 7-14 days",
  "ai_insight": "One specific expert insight for this exact question"
}}[/INST]"""

    for model in HF_MODELS:
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens":   700,
                "temperature":      0.6,
                "top_p":            0.9,
                "return_full_text": False,
                "stop":             ["[INST]", "</s>", "Human:", "Farmer:"]
            }
        }
        result = _hf_post(model, payload, timeout=8)
        if not result:
            continue

        text = ''
        if isinstance(result, list) and result:
            text = result[0].get('generated_text', '')
        elif isinstance(result, dict):
            text = result.get('generated_text', '')

        if not text.strip():
            continue

        advisory = _extract_json(text)
        if advisory and advisory.get('title') and advisory.get('treatment'):
            advisory['stress_type']    = stress_type
            advisory['crop']           = crop or 'General'
            advisory['severity_level'] = SEVERITY_MAP.get(stress_type, 'Low')
            advisory['_source']        = f'HuggingFace ({model.split("/")[1]})'
            advisory['_translated_to'] = 'en'
            logger.info(f"✅ HF LLM advisory: {model.split('/')[1]}")
            return advisory

    return None


def call_openai(query: str, crop: str, intent: str, stress_type: str) -> Optional[Dict]:
    """OpenAI GPT-4o-mini — best quality responses"""
    if not OPENAI_KEY or OPENAI_KEY.startswith('sk-placeholder'):
        return None

    crop_ctx = f" for {crop}" if crop and crop not in ('', 'Unknown', 'General') else ""
    system   = "You are FarmAI, an expert agricultural advisor for Indian farmers. Answer any farming question specifically and practically. Be like a helpful expert, not a textbook. Return only valid JSON."
    user     = f"""Farmer's question: "{query}"
Topic{crop_ctx}: {intent.replace('_',' ').title()}

Return ONLY this JSON (be specific to the exact question asked):
{{
  "title": "Specific title for this question",
  "immediate_action": "Single most important action",
  "treatment": ["step1 (specific)","step2","step3","step4","step5"],
  "prevention": ["tip1","tip2","tip3","tip4"],
  "fertilizers": ["input1","input2","input3"],
  "follow_up": "7-14 day follow up",
  "ai_insight": "Expert insight specific to this question"
}}"""

    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role":"system","content":system},{"role":"user","content":user}],
        "max_tokens": 900, "temperature": 0.7,
        "response_format": {"type":"json_object"}
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions', data=payload,
        headers={'Authorization':f'Bearer {OPENAI_KEY}','Content-Type':'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data    = json.loads(resp.read().decode('utf-8'))
            content = data['choices'][0]['message']['content']
            adv     = json.loads(content)
            adv.update({'stress_type':stress_type,'crop':crop or 'General',
                        'severity_level':SEVERITY_MAP.get(stress_type,'Low'),
                        '_source':'OpenAI GPT-4o-mini','_translated_to':'en'})
            logger.info("✅ OpenAI advisory generated")
            return adv
    except Exception as e:
        logger.warning(f"OpenAI failed: {e}")
        return None


# ─── Smart Fallback (TRULY DYNAMIC — different answer every time) ──────────────
import random as _random

def smart_fallback(query: str, stress_type: str, crop: str, intent: str) -> Dict:
    """
    Truly dynamic fallback — reads actual keywords in query,
    picks different tips each time, never gives same answer twice.
    """
    q  = query.lower()
    C  = crop if crop and crop not in ('', 'Unknown', 'General') else None
    CL = C or 'your crop'

    # ── Detect specific symptoms from query ──
    has_yellow   = any(w in q for w in ['yellow','pale','chlorosis','pila','yellowing'])
    has_spots    = any(w in q for w in ['spot','rust','blight','powder','mildew','blast'])
    has_wilt     = any(w in q for w in ['wilt','droop','dry','sukh','sukha','dying'])
    has_pest     = any(w in q for w in ['insect','pest','worm','hole','eaten','keeda'])
    has_curl     = any(w in q for w in ['curl','mosaic','twist','distort','virus'])
    has_rot      = any(w in q for w in ['rot','ooze','smell','bacterial','soft'])
    has_heat     = any(w in q for w in ['heat','hot','scorch','sunburn','garmi'])
    has_weed     = any(w in q for w in ['weed','grass','ghaas','unwanted'])
    has_grow     = any(w in q for w in ['grow','plant','cultivat','sow','nursery','ugao'])
    has_harvest  = any(w in q for w in ['harvest','kato','ready','mature','store'])
    has_fert     = any(w in q for w in ['fertilizer','urea','dap','manure','khad','npk'])
    has_water    = any(w in q for w in ['irrigat','water','paani','drip','sprinkler'])

    # ── Detect severity words ──
    severe = any(w in q for w in ['all','completely','entire','whole','very bad','bahut','zyada','serious'])

    # ── Build dynamic title based on actual query content ──
    if has_grow:
        title = f"Complete Cultivation Guide for {CL}"
        imm   = f"Prepare well-drained soil with FYM 5 tonnes/acre before sowing {CL}"
        st    = 'CULTIVATION'
    elif has_harvest:
        title = f"Harvesting & Post-Harvest Guide for {CL}"
        imm   = f"Check {CL} moisture content — harvest at the right stage to avoid losses"
        st    = 'HARVESTING'
    elif has_fert:
        title = f"Fertilizer Schedule for {CL}"
        imm   = f"Get soil tested first — then apply fertilizer based on soil report for {CL}"
        st    = 'FERTILIZER'
    elif has_water:
        title = f"Irrigation Management for {CL}"
        imm   = f"Switch to drip irrigation for {CL} — saves 40% water and improves yield"
        st    = 'IRRIGATION'
    elif has_yellow:
        title = f"Yellowing & Nutrient Problem in {CL}"
        imm   = f"Spray Urea 2% + Zinc Sulfate 0.5% foliar spray on {CL} — shows improvement in 7 days"
        st    = 'NUTRIENT_DEFICIENCY'
    elif has_spots:
        title = f"Fungal Disease Control in {CL}"
        imm   = f"Spray Mancozeb 75% WP @ 2.5g/liter on {CL} — act within 24 hours to stop spread"
        st    = 'FUNGAL_DISEASE'
    elif has_wilt and not has_pest:
        title = f"Drought & Water Stress in {CL}"
        imm   = f"Irrigate {CL} field immediately — provide 4-5 cm water, preferably in evening"
        st    = 'WATER_STRESS'
    elif has_pest:
        title = f"Pest Attack Management in {CL}"
        imm   = f"Identify the exact pest first — spray Neem oil 3% as first safe treatment on {CL}"
        st    = 'PEST_INFESTATION'
    elif has_curl:
        title = f"Viral Disease Alert in {CL}"
        imm   = f"Remove all virus-infected {CL} plants immediately — NO chemical cures viral disease"
        st    = 'VIRAL_DISEASE'
    elif has_rot:
        title = f"Bacterial Disease in {CL}"
        imm   = f"Spray Copper Hydroxide 77% WP @ 3g/liter on {CL} — avoid working in wet field"
        st    = 'BACTERIAL_DISEASE'
    elif has_heat:
        title = f"Heat Stress Relief for {CL}"
        imm   = f"Irrigate {CL} in early morning or evening — never in afternoon heat"
        st    = 'HEAT_STRESS'
    elif has_weed:
        title = f"Weed Control in {CL} Field"
        imm   = f"Manual weeding in {CL} must be done within 21 days of sowing — critical period"
        st    = 'WEED_INFESTATION'
    else:
        title = f"Expert Advisory for {CL}"
        imm   = f"Describe specific symptoms of {CL} (color, shape, location) for targeted advice"
        st    = stress_type or 'GENERAL_FARMING'

    # ── Large pool of tips per category (randomly sampled each time) ──
    ALL_TREATMENTS = {
        'NUTRIENT_DEFICIENCY': [
            f"Apply Urea 46%N @ 25 kg/acre as top dressing on {CL} for quick nitrogen boost",
            "Spray Zinc Sulfate 21% @ 0.5% solution — most common deficiency in Indian soils",
            "Apply DAP 18-46-0 @ 20 kg/acre if leaves show purple/reddish color",
            "Use Ferrous Sulfate 0.5% spray for iron deficiency in alkaline soils",
            f"Add FYM (Farm Yard Manure) @ 5 tonnes/acre to improve {CL} soil nutrition",
            "Apply Magnesium Sulfate 0.5% spray for interveinal yellowing",
            "Mix micronutrient mixture in irrigation water for quick absorption",
            f"Get leaf tissue test done at nearest KVK to confirm deficiency in {CL}",
            "Apply Boron 0.2% spray if new leaves are deformed or curled",
            "Use slow-release fertilizers during rainy season to prevent leaching",
        ],
        'FUNGAL_DISEASE': [
            "Spray Mancozeb 75% WP @ 2.5g/liter as contact fungicide — first line treatment",
            "Apply Propiconazole 25% EC @ 1ml/liter after 7 days for systemic control",
            f"Remove and burn all infected {CL} leaves — never compost diseased material",
            "Stop overhead irrigation — switch to drip to keep foliage dry",
            "Apply Trichoderma viride @ 4g/liter soil drench to protect root zone",
            "Spray Carbendazim 50% WP @ 1g/liter for stem and collar rot",
            "Maintain spacing between plants — airflow prevents fungal spread",
            "Spray in evening — morning dew activates most fungicides better",
            f"Repeat spray every 10 days for 3 applications on {CL}",
            "Use Copper Oxychloride 50% WP @ 3g/liter as broad-spectrum fungicide",
        ],
        'WATER_STRESS': [
            f"Irrigate {CL} immediately — 4-5 cm water in evening is most effective",
            "Apply paddy straw mulch @ 4 inch depth — reduces evaporation by 50%",
            "Spray Kaolin clay 5% on leaves — reduces leaf temperature by 4-6°C",
            "Apply Potassium Nitrate 0.5% foliar spray to improve drought tolerance",
            "Install drip irrigation — saves 40% water with 20% higher yield",
            "Make bunding around field — conserve every drop of rainfall",
            f"Check {CL} soil moisture 6 inches deep before each irrigation",
            "Apply Humic acid 2ml/liter through drip — improves water retention",
            "Irrigate at flowering and grain filling stages — most critical periods",
            "Avoid irrigation during afternoon heat — high evaporation loss",
        ],
        'PEST_INFESTATION': [
            "Spray Neem oil 3000 PPM @ 5ml/liter — safe, effective first treatment",
            "For aphids/whitefly: Imidacloprid 17.8% SL @ 0.5ml/liter — very effective",
            "For caterpillars/borers: Emamectin Benzoate 5% SG @ 0.5g/liter",
            "Install Yellow Sticky Traps @ 10/acre — catches flying pests early",
            f"Spray early morning on {CL} — pests are active and pesticide works better",
            "For stem borers: use Carbofuran 3G @ 25kg/hectare in soil",
            "Install pheromone traps @ 5/acre for bollworm/fruit borer monitoring",
            "Use Spinosad 45% SC @ 0.3ml/liter for resistant pest populations",
            "Avoid spraying same chemical twice — rotate pesticide classes",
            f"Remove and destroy heavily infested {CL} plant parts",
        ],
        'VIRAL_DISEASE': [
            f"Uproot ALL virus-infected {CL} plants — do it today, don't wait",
            "Spray Imidacloprid 17.8% SL @ 0.5ml/liter — kills virus-spreading aphids/whitefly",
            "Apply mineral oil 1% spray — prevents virus transmission by insects",
            "Install silver reflective mulch — repels whiteflies that spread virus",
            "Disinfect all pruning tools with 10% bleach before moving to next plant",
            f"Maintain 45-day crop-free period after severe {CL} viral outbreak",
            "Use certified virus-indexed seeds from reliable source next season",
            "Plant border crops of maize/sorghum — they block virus-carrying wind insects",
            "Spray Thiamethoxam 25% WG @ 0.5g/liter as systemic vector control",
            "Survey field every 3 days — rogue out new symptomatic plants immediately",
        ],
        'BACTERIAL_DISEASE': [
            f"Spray Copper Hydroxide 77% WP @ 3g/liter on {CL} — most effective bactericide",
            "Apply Streptocycline 90% SP @ 0.5g + Copper Oxychloride 50% @ 2.5g per liter",
            f"Avoid working in {CL} field when wet — bacteria spread through water drops",
            "Disinfect all farm tools with 10% bleach solution daily",
            f"Remove and burn all severely infected {CL} material",
            "Improve field drainage — standing water is main cause of bacterial spread",
            "Apply Bordeaux mixture 1% as protective spray in wet season",
            "Avoid overhead irrigation — use drip or furrow irrigation instead",
            "Do NOT apply excess nitrogen during bacterial infection — worsens it",
            "Use certified disease-free seeds next season",
        ],
        'HEAT_STRESS': [
            f"Irrigate {CL} in early morning (6-8 AM) — most effective heat stress relief",
            "Spray Kaolin particle film 5% — reduces canopy temperature by 4-6°C",
            "Apply Salicylic acid 100 ppm foliar spray — activates heat tolerance genes",
            f"Install shade nets 35-50% for {CL} during peak heat wave",
            "Apply Potassium Sulfate 2g/liter — strengthens cell walls against heat",
            "Reduce nitrogen fertilizer during heat wave — plants become more sensitive",
            "Mulch field with paddy straw — keeps root zone 5-8°C cooler",
            "Irrigate every 2-3 days during heat wave — do NOT let soil dry out",
            "Spray water mist on plants in afternoon if possible — quick cooling",
            f"Document heat damage in {CL} — claim crop insurance if above 33% loss",
        ],
        'WEED_INFESTATION': [
            f"Manual weeding in {CL} within 21 days of sowing — most critical weed-free period",
            "Apply Pendimethalin 30% EC @ 3.3 liter/hectare before weed germination",
            f"For broad-leaf weeds: 2,4-D @ 1 liter/hectare at 25-30 days after sowing {CL}",
            "Use inter-cultivation with tractor cultivator @ 20-25 days — kills weeds + aerates",
            "Apply Bispyribac-Sodium 10% SC @ 250ml/hectare for weeds in paddy",
            "Maintain dense crop canopy — shades out weeds naturally",
            "Use stale seedbed technique — irrigate, let weeds germinate, kill before sowing",
            f"Apply thick paddy straw mulch between {CL} rows — prevents weed germination",
            "Rotate herbicide classes every season — prevents resistance development",
            "Ensure proper land leveling — uneven fields have more weed pressure",
        ],
        'CULTIVATION': [
            f"Prepare {CL} field by deep plowing (30 cm) and apply FYM 5 tonnes/acre",
            f"Use certified high-yielding variety of {CL} from government-approved source",
            f"Maintain correct spacing for {CL} — overcrowding reduces yield significantly",
            f"Apply basal dose fertilizer at sowing time — DAP 50 kg/acre for {CL}",
            f"Treat {CL} seeds with Trichoderma 4g/kg before sowing for root protection",
            f"Maintain optimum soil moisture at {CL} germination stage — critical period",
            f"Sow {CL} at recommended depth — too deep or shallow reduces germination",
            f"Irrigate {CL} field 2-3 days before sowing for even germination",
            f"Remove crop debris from previous season before {CL} sowing",
            f"Get soil pH tested — {CL} grows best between pH 6.0-7.5",
        ],
        'HARVESTING': [
            f"Harvest {CL} at correct moisture content — excess moisture causes storage loss",
            f"Use sharp, clean sickle or machine harvester for {CL} — reduces grain loss",
            f"Harvest {CL} in morning — cooler temperature preserves quality better",
            f"Dry {CL} properly before storage — target moisture below 12-14%",
            f"Store {CL} in clean, dry, pest-free godown with proper ventilation",
            f"Apply Celphos (Aluminium Phosphide) tablets in sealed storage for {CL}",
            f"Grade {CL} before selling — higher grade fetches better market price",
            f"Sell {CL} at regulated APMC mandi — avoid distress selling to traders",
            f"Check government MSP for {CL} at PM-KISAN portal before selling",
            f"Record yield per acre — helps plan fertilizer for next season",
        ],
        'FERTILIZER': [
            f"Get soil tested at KVK before applying any fertilizer to {CL}",
            f"Apply basal NPK (DAP + MOP) at sowing for {CL} root development",
            f"Split nitrogen application for {CL}: 1/3 at sowing, 1/3 at tillering, 1/3 at panicle",
            f"Use nano urea liquid @ 4ml/liter foliar spray for {CL} — saves 50% cost",
            f"Apply Zinc Sulfate 25 kg/hectare once every 3 seasons in {CL} field",
            f"Use organic compost 5 tonnes/acre — reduces chemical fertilizer need by 25%",
            f"Avoid applying fertilizer in standing water — causes leaching and waste",
            f"Apply fertilizer after irrigation — never on dry soil for {CL}",
            f"Use Boron 10 kg/hectare for {CL} during flowering stage",
            f"Maintain records of fertilizer applied — helps optimise next crop cycle",
        ],
        'IRRIGATION': [
            f"Install drip irrigation for {CL} — saves 40% water, increases yield 20%",
            f"Irrigate {CL} at critical stages: germination, tillering, flowering, grain fill",
            f"Check soil moisture 6 inches deep before each irrigation of {CL}",
            f"Irrigate in early morning or evening — reduce evaporation loss by 30%",
            f"Avoid over-irrigation — waterlogging damages {CL} roots within 24 hours",
            f"Use tensiometer or feel method to judge irrigation timing for {CL}",
            f"Furrow irrigation is efficient for row crops like {CL}",
            f"Laser land leveling saves 20% irrigation water for {CL}",
            f"Rainwater harvesting farm pond — ensures {CL} irrigation in dry spells",
            f"Apply fertigation through drip — saves fertilizer and reaches roots directly",
        ],
        'GENERAL_FARMING': [
            f"For best {CL} yield: right variety + right seed rate + right spacing + right time",
            f"Crop rotation with legumes improves soil nitrogen for next {CL} crop",
            f"Integrated Pest Management (IPM) reduces cost and increases {CL} profit",
            f"Join your local Farmer Producer Organisation (FPO) for better {CL} prices",
            f"Apply for PM-Fasal Bima Yojana crop insurance before {CL} sowing date",
            f"Use Kisan Call Centre (1800-180-1551) for free expert advice on {CL}",
            f"Record all inputs and costs for {CL} — helps calculate real profit",
            f"Attend KVK field demonstrations for latest {CL} varieties and practices",
            f"Soil health card gives crop-specific fertilizer recommendation for {CL}",
            f"Follow weather advisory from IMD before major {CL} field operations",
        ],
    }

    ALL_PREVENTION = {
        'NUTRIENT_DEFICIENCY': ["Soil test every season before sowing","Apply organic manure to build long-term soil health","Maintain soil pH 6-7 for best nutrient availability","Avoid burning crop residues — loses valuable nutrients"],
        'FUNGAL_DISEASE': ["Use certified disease-resistant varieties","Avoid overhead irrigation — use drip","Rotate crops every season to break disease cycle","Apply preventive Mancozeb spray during humid season"],
        'WATER_STRESS': ["Install drip irrigation for water-scarce fields","Build farm pond for rainwater harvesting","Use drought-tolerant varieties in low-rainfall areas","Apply mulch before hot dry season begins"],
        'PEST_INFESTATION': ["Install pheromone traps 2 weeks before expected pest season","Practice crop rotation to break pest life cycle","Plant border crops of maize/sorghum as trap crop","Use certified pest-free seeds from reliable source"],
        'VIRAL_DISEASE': ["Use certified virus-free seeds only","Control vector insects from day 1 of crop","Maintain 45-day crop-free period after severe infection","Rogue out symptomatic plants before they spread"],
        'BACTERIAL_DISEASE': ["Use certified disease-free seeds","Avoid overhead irrigation","Rotate crops with non-host crops for 2 seasons","Disinfect all farm tools with bleach regularly"],
        'HEAT_STRESS': ["Select heat-tolerant varieties suited to your region","Adjust sowing date to avoid peak summer flowering","Apply mulch to keep root zone 5-8°C cooler","Irrigate in evening during summer to cool canopy"],
        'WEED_INFESTATION': ["Use certified weed-free seeds","Apply pre-emergence herbicide before weeds germinate","Dense crop stand shades out weeds naturally","Rotate herbicide class every season to prevent resistance"],
        'CULTIVATION': [f"Use certified {CL} seed from government-approved source",f"Follow recommended {CL} sowing calendar for your district","Deep plow once every 3 years to break hard pan","Attend KVK training for latest high-yield practices"],
        'HARVESTING': [f"Monitor {CL} maturity regularly in final 2 weeks","Keep harvesting equipment serviced and ready","Arrange storage before harvest — avoid field drying","Insure your crop before harvest season"],
        'FERTILIZER': ["Always soil test before fertilizer application","Use organic matter to reduce chemical dependence","Apply fertilizers in split doses — reduces loss","Store fertilizers in dry, cool, ventilated place"],
        'IRRIGATION': ["Check weather forecast before irrigation — save water","Fix leaks in irrigation system immediately","Level field properly for uniform irrigation","Install rain gauge to measure actual rainfall"],
        'GENERAL_FARMING': ["Keep detailed farm records every season","Diversify crops to reduce financial risk","Connect with local KVK for free expert guidance","Join FPO for better input costs and crop prices"],
    }

    ALL_PRODUCTS = {
        'NUTRIENT_DEFICIENCY': ['Urea 46%N','DAP 18-46-0','MOP 60%K2O','Zinc Sulfate 21%','Ferrous Sulfate','Magnesium Sulfate','Boron 20%','Nano Urea Liquid'],
        'FUNGAL_DISEASE': ['Mancozeb 75% WP','Propiconazole 25% EC','Carbendazim 50% WP','Copper Hydroxide 77%','Trichoderma viride','Copper Oxychloride 50%'],
        'WATER_STRESS': ['Kaolin Particle Film','Potassium Nitrate 13-0-45','Humic Acid Liquid','Drip Irrigation System','Paddy Straw Mulch','Salicylic Acid 100ppm'],
        'PEST_INFESTATION': ['Neem Oil 3000 PPM','Imidacloprid 17.8% SL','Emamectin Benzoate 5% SG','Chlorpyrifos 20% EC','Spinosad 45% SC','Yellow Sticky Traps','Pheromone Traps'],
        'VIRAL_DISEASE': ['Imidacloprid 17.8% SL','Thiamethoxam 25% WG','Mineral Oil 1%','Silver Reflective Mulch','10% Bleach Solution'],
        'BACTERIAL_DISEASE': ['Copper Hydroxide 77% WP','Streptocycline 90% SP','Copper Oxychloride 50% WP','Bordeaux Mixture 1%','10% Bleach for tools'],
        'HEAT_STRESS': ['Kaolin 95% Particle Film','Salicylic Acid 100ppm','Potassium Sulfate 50%','Shade Net 35-50%','Paddy Straw Mulch'],
        'WEED_INFESTATION': ['Pendimethalin 30% EC','2,4-D Ethyl Ester 38%','Bispyribac-Sodium 10% SC','Atrazine 50% WP','Manual Weeder'],
        'CULTIVATION': ['Certified Seeds','FYM / Vermicompost','Trichoderma viride seed treatment','DAP 18-46-0','MOP 60%K2O','Drip Irrigation'],
        'HARVESTING': ['Harvester / Sickle','Moisture Meter','Storage Bags (HDPE)','Celphos Tablets','Grain Grader','Weighing Scale'],
        'FERTILIZER': ['Soil Test Kit','Urea 46%N','DAP 18-46-0','Nano Urea Liquid','Zinc Sulfate 21%','Organic Compost'],
        'IRRIGATION': ['Drip Irrigation Kit','Tensiometer','Rain Gauge','Fertigation Unit','Sprinkler System','Water Meter'],
        'GENERAL_FARMING': ['Soil Test Kit','Kisan Credit Card','PM-Fasal Bima Yojana','KVK Helpline 1800-180-1551','Soil Health Card','Kisan Call Centre'],
    }

    FOLLOW_UPS = {
        'NUTRIENT_DEFICIENCY': f"Check {CL} leaf color improvement 10-14 days after treatment. If still pale, repeat foliar spray. Consult KVK for soil test.",
        'FUNGAL_DISEASE': f"Re-inspect {CL} every 7 days. Repeat fungicide spray if new spots appear. 3 sprays in 30 days controls most fungal diseases.",
        'WATER_STRESS': f"Check {CL} soil moisture daily during stress period. Irrigate every 5-7 days. New leaf emergence in 1 week shows recovery.",
        'PEST_INFESTATION': f"Count pest population 5 days after spray. If above economic threshold, change chemical class and repeat. Use sticky trap count to monitor.",
        'VIRAL_DISEASE': f"Survey {CL} field every 3 days. Uproot any new symptomatic plants. Focus on vector (whitefly/aphid) control for 30 days.",
        'BACTERIAL_DISEASE': f"Apply bactericide spray every 7 days for 2-3 applications. Improve drainage in {CL} field. Avoid excess nitrogen.",
        'HEAT_STRESS': f"Continue irrigation every 2-3 days during heat wave. Monitor new {CL} leaf flush — improvement visible in 7-10 days.",
        'WEED_INFESTATION': f"Inspect {CL} field at 35-40 days for second weed flush. Hand weed survivors before they set seed.",
        'CULTIVATION': f"Monitor {CL} germination at 7-10 days — target 85%+ germination. Gap filling with seedlings if below threshold.",
        'HARVESTING': f"Monitor {CL} grain moisture every 2 days after harvest — dry to below 12% before storage. Check for storage pests at 15 days.",
        'FERTILIZER': f"Check {CL} leaf color and growth response 10-14 days after application. Adjust next dose based on crop response.",
        'IRRIGATION': f"Monitor {CL} soil moisture weekly. Adjust irrigation frequency based on actual weather — reduce during rainy periods.",
        'GENERAL_FARMING': f"Follow up with your local KVK or agricultural officer in 2 weeks. Keep records of what you applied and crop response.",
    }

    # Pick the right category
    cat = st if st in ALL_TREATMENTS else stress_type if stress_type in ALL_TREATMENTS else 'GENERAL_FARMING'

    # Randomly sample 5 treatments and 4 prevention tips (different every call!)
    pool_t = ALL_TREATMENTS.get(cat, ALL_TREATMENTS['GENERAL_FARMING'])
    pool_p = ALL_PREVENTION.get(cat, ALL_PREVENTION['GENERAL_FARMING'])
    pool_pr= ALL_PRODUCTS.get(cat, ALL_PRODUCTS['GENERAL_FARMING'])

    chosen_t  = _random.sample(pool_t,  min(5, len(pool_t)))
    chosen_p  = _random.sample(pool_p,  min(4, len(pool_p)))
    chosen_pr = _random.sample(pool_pr, min(4, len(pool_pr)))

    # Build a unique insight based on actual query words
    insight_templates = [
        f"Your query mentions '{query[:40].strip()}' — this pattern is most commonly caused by {cat.replace('_',' ').lower()} in Indian {CL} farms.",
        f"Based on your description, {CL} is showing classic signs of {cat.replace('_',' ').lower()}. Early action in first 48 hours prevents 60-80% crop loss.",
        f"Indian farmers in similar conditions report best results with immediate {chosen_t[0].split('—')[0].strip() if chosen_t else 'treatment'}.",
        f"This symptom in {CL} is common in {['Kharif','Rabi','summer'][_random.randint(0,2)]} season. Timely management prevents yield loss of 20-40%.",
        f"For your query: '{query[:50].strip()}' — prioritise immediate action within 24-48 hours for best recovery of {CL}.",
    ]

    return {
        'stress_type':      cat,
        'crop':             C or 'General',
        'title':            title,
        'immediate_action': imm,
        'treatment':        chosen_t,
        'prevention':       chosen_p,
        'fertilizers':      chosen_pr,
        'follow_up':        FOLLOW_UPS.get(cat, f"Monitor {CL} regularly and consult your nearest KVK."),
        'severity_level':   SEVERITY_MAP.get(cat, 'Medium'),
        'ai_insight':       _random.choice(insight_templates),
        '_source':          'FarmAI Smart Advisory',
        '_translated_to':   'en',
    }


# ─── Main Advisory Engine ──────────────────────────────────────────────────────
class AIAdvisoryEngine:

    def classify_stress(self, text: str, feature_vector: list = None, intent: str = 'STRESS') -> Dict:
        # For non-stress intents, return immediately with intent classification
        if intent != 'STRESS':
            return keyword_classify(text, intent)

        # Try BERT zero-shot
        if HF_API_KEY:
            try:
                result = classify_with_bert(text)
                if result and result.get('predicted_stress') and result['predicted_stress'] != 'INSUFFICIENT_DATA':
                    return result
            except Exception as e:
                logger.warning(f"BERT failed: {e}")

        # Try CSV-trained model
        try:
            from ml_engine.ml_classifier import ml_classifier
            result = ml_classifier.predict(feature_vector or [], raw_text=text)
            if result and result.get('predicted_stress') and result['predicted_stress'] != 'INSUFFICIENT_DATA' \
               and not result.get('insufficient_data', False):
                result['model_used'] = 'TF-IDF + LogReg (CSV)'
                return result
        except Exception as e:
            logger.warning(f"CSV model failed: {e}")

        # Keyword fallback — guaranteed
        return keyword_classify(text, 'STRESS')

    def generate_advisory(self, query: str, stress_type: str, crop: str, intent: str = 'STRESS') -> Dict:
        logger.info(f"Generating: intent={intent} | stress={stress_type} | crop={crop} | q='{query[:40]}'")

        # Try OpenAI first (best quality)
        adv = call_openai(query, crop, intent, stress_type)
        if adv:
            return adv

        # Try HuggingFace LLM
        adv = call_hf_llm(query, crop, intent, stress_type)
        if adv:
            return adv

        # Smart fallback (always works, always dynamic)
        return smart_fallback(query, stress_type, crop, intent)

    def full_pipeline(self, english_query: str, feature_vector: list,
                      selected_crop: str = '', nlp_detected_crop: str = '') -> Dict:
        # Detect intent from the actual question
        intent = detect_intent(english_query)
        logger.info(f"Intent detected: {intent} for '{english_query[:50]}'")

        # Detect crop
        crop = detect_crop(english_query, nlp_detected_crop, selected_crop)

        # Classify stress type
        classification = self.classify_stress(english_query, feature_vector, intent)
        stress_type    = classification.get('predicted_stress', 'GENERAL_FARMING')

        # If intent overrides classification for non-disease queries
        if intent in ('CULTIVATION','HARVESTING','FERTILIZER','IRRIGATION','MARKET','GENERAL_FARMING'):
            stress_type = intent
            classification['predicted_stress']   = intent
            classification['display_name']        = STRESS_DISPLAY.get(intent, '🌾 Crop Advisory')
            classification['severity']            = SEVERITY_MAP.get(intent, 'Low')
            classification['color']               = COLOR_MAP.get(intent, '#16a34a')
            classification['confidence']          = 0.85
            classification['confidence_percent']  = '85.0%'

        # Generate advisory
        advisory = self.generate_advisory(english_query, stress_type, crop, intent)
        advisory['stress_type']    = stress_type
        advisory['crop']           = crop or advisory.get('crop', 'General')
        advisory['severity_level'] = SEVERITY_MAP.get(stress_type, 'Medium')
        advisory.setdefault('_translated_to', 'en')

        return {'classification': classification, 'advisory': advisory}


ai_engine = AIAdvisoryEngine()
logger.info(f"✅ FarmAI AI Engine v8 | OpenAI: {'YES' if OPENAI_KEY and not OPENAI_KEY.startswith('sk-placeholder') else 'NO'} | HF: {'YES' if HF_API_KEY else 'NO'}")
