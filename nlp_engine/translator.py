"""
Translation Engine v3 — Farmer Advisory System
Uses MyMemory REST API (free, no API key, supports all Indian languages)
as primary, with Unicode script detection fallback.

Flow:
  1. Detect input language (Unicode script ranges — works offline)
  2. If non-English → POST to MyMemory API to get English text
  3. NLP+ML process the English text
  4. Translate advisory back to user language via MyMemory API
"""

import re
import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)

# ─── Language maps ─────────────────────────────────────────────────────────────
# Web Speech API lang code  →  MyMemory lang pair code
SPEECH_TO_MYMEMORY = {
    'en-IN': 'en', 'en-US': 'en', 'en-GB': 'en',
    'hi-IN': 'hi',   # Hindi
    'te-IN': 'te',   # Telugu
    'ta-IN': 'ta',   # Tamil
    'kn-IN': 'kn',   # Kannada
    'mr-IN': 'mr',   # Marathi
    'pa-IN': 'pa',   # Punjabi
    'gu-IN': 'gu',   # Gujarati
    'bn-IN': 'bn',   # Bengali
    'ml-IN': 'ml',   # Malayalam
    'or-IN': 'or',   # Odia
}

LANG_NAMES = {
    'en': 'English', 'hi': 'Hindi', 'te': 'Telugu', 'ta': 'Tamil',
    'kn': 'Kannada', 'mr': 'Marathi', 'pa': 'Punjabi', 'gu': 'Gujarati',
    'bn': 'Bengali', 'ml': 'Malayalam', 'or': 'Odia',
}

# MyMemory API endpoint
MYMEMORY_URL = "https://api.mymemory.translated.net/get"


# ─── Script-based language detection (100% offline) ────────────────────────────
def _detect_by_script(text: str) -> str:
    """Detect language from Unicode character ranges — no API needed."""
    counts = {
        'hi': len(re.findall(r'[\u0900-\u097F]', text)),  # Devanagari (Hindi/Marathi)
        'te': len(re.findall(r'[\u0C00-\u0C7F]', text)),  # Telugu
        'ta': len(re.findall(r'[\u0B80-\u0BFF]', text)),  # Tamil
        'kn': len(re.findall(r'[\u0C80-\u0CFF]', text)),  # Kannada
        'ml': len(re.findall(r'[\u0D00-\u0D7F]', text)),  # Malayalam
        'bn': len(re.findall(r'[\u0980-\u09FF]', text)),  # Bengali
        'gu': len(re.findall(r'[\u0A80-\u0AFF]', text)),  # Gujarati
        'pa': len(re.findall(r'[\u0A00-\u0A7F]', text)),  # Gurmukhi (Punjabi)
        'or': len(re.findall(r'[\u0B00-\u0B7F]', text)),  # Odia
    }
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else 'en'


def detect_language(text: str, hint_lang: str = 'auto') -> str:
    """
    Detect input language.
    hint_lang: value from Web Speech API lang selector (e.g. 'hi-IN')
    """
    if not text or not text.strip():
        return 'en'

    # If user explicitly selected a non-English language, trust it
    if hint_lang and hint_lang not in ('auto', 'en-IN', 'en-US', 'en-GB', ''):
        code = SPEECH_TO_MYMEMORY.get(hint_lang, hint_lang.split('-')[0])
        logger.info(f"Lang from UI selector: {hint_lang} → {code}")
        return code

    # Otherwise detect from Unicode script
    detected = _detect_by_script(text)
    logger.info(f"Script detection: '{text[:30]}…' → {detected}")
    return detected


# ─── MyMemory Translation API ──────────────────────────────────────────────────
def _mymemory_translate(text: str, src_lang: str, tgt_lang: str) -> str:
    """
    Call MyMemory REST API.
    Returns translated string, or original text on failure.
    """
    if not text or not text.strip():
        return text
    if src_lang == tgt_lang:
        return text

    try:
        lang_pair = f"{src_lang}|{tgt_lang}"
        params = urllib.parse.urlencode({
            'q':        text,
            'langpair': lang_pair,
            'de':       'farmai@example.com'   # optional email for higher rate limits
        })
        url = f"{MYMEMORY_URL}?{params}"

        req = urllib.request.Request(url, headers={'User-Agent': 'FarmAI/2.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        # MyMemory response format
        if data.get('responseStatus') == 200:
            translated = data['responseData']['translatedText']
            # MyMemory returns "MYMEMORY WARNING" text on quota issues
            if 'MYMEMORY WARNING' in translated or 'YOU USED ALL AVAILABLE FREE TRANSLATIONS' in translated:
                logger.warning("MyMemory quota reached — returning original text")
                return text
            logger.info(f"MyMemory [{src_lang}→{tgt_lang}]: '{text[:40]}' → '{translated[:40]}'")
            return translated
        else:
            logger.warning(f"MyMemory status {data.get('responseStatus')}: {data.get('responseDetails','')}")
            return text

    except Exception as e:
        logger.error(f"MyMemory API error: {e}")
        return text


# ─── Public functions ──────────────────────────────────────────────────────────

def translate_to_english(text: str, source_lang: str = 'auto') -> dict:
    """
    Translate any Indian language text to English.

    Returns dict:
      translated       : English text (or original if already English)
      original         : original input
      source_lang      : detected lang code ('hi', 'te', etc.)
      source_lang_name : display name ('Hindi', 'Telugu', etc.)
      was_translated   : bool
    """
    if not text or not text.strip():
        return {
            'translated': text, 'original': text,
            'source_lang': 'en', 'source_lang_name': 'English',
            'was_translated': False
        }

    detected = detect_language(text, hint_lang=source_lang)

    if detected == 'en':
        return {
            'translated': text, 'original': text,
            'source_lang': 'en', 'source_lang_name': 'English',
            'was_translated': False
        }

    english_text = _mymemory_translate(text, src_lang=detected, tgt_lang='en')
    was_translated = (english_text.strip().lower() != text.strip().lower())

    return {
        'translated':       english_text,
        'original':         text,
        'source_lang':      detected,
        'source_lang_name': LANG_NAMES.get(detected, detected),
        'was_translated':   was_translated,
    }


def translate_text_to_language(text: str, target_lang: str) -> str:
    """Translate a single English string to target_lang."""
    if not text or not target_lang or target_lang == 'en':
        return text
    return _mymemory_translate(text, src_lang='en', tgt_lang=target_lang)


def translate_advisory_to_language(advisory_dict: dict, target_lang: str) -> dict:
    """
    Translate a full advisory dict from English back to the farmer's language.
    Translates: title, immediate_action, treatment[], prevention[], follow_up
    """
    if not target_lang or target_lang == 'en' or not advisory_dict:
        return advisory_dict

    def _t(s):
        if not s or not isinstance(s, str):
            return s
        return _mymemory_translate(s, 'en', target_lang)

    def _tlist(lst):
        if not lst or not isinstance(lst, list):
            return lst
        return [_t(item) for item in lst]

    try:
        result = dict(advisory_dict)
        result['title']            = _t(advisory_dict.get('title', ''))
        result['immediate_action'] = _t(advisory_dict.get('immediate_action', ''))
        result['treatment']        = _tlist(advisory_dict.get('treatment', []))
        result['prevention']       = _tlist(advisory_dict.get('prevention', []))
        result['follow_up']        = _t(advisory_dict.get('follow_up', ''))
        result['_translated_to']   = target_lang
        result['_translated_to_name'] = LANG_NAMES.get(target_lang, target_lang)
        logger.info(f"Advisory translated to {target_lang} ({LANG_NAMES.get(target_lang)})")
        return result
    except Exception as e:
        logger.error(f"Advisory translation error: {e}")
        return advisory_dict


# Expose LANG_MAP for compatibility
LANG_MAP = SPEECH_TO_MYMEMORY
