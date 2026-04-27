"""
NLP Processing Engine v2
Handles text preprocessing, tokenization, stopword removal, and feature extraction.
Now includes: weed detection, stricter minimum token requirement, better scoring.
"""
import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer, PorterStemmer
    for resource in ['punkt', 'punkt_tab', 'stopwords', 'wordnet', 'omw-1.4']:
        try:
            nltk.download(resource, quiet=True)
        except Exception:
            pass
    NLTK_AVAILABLE = True
    logger.info("✅ NLTK loaded")
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("⚠️  NLTK not available")

# ─── Domain Vocabulary ─────────────────────────────────────────────────────────

CROP_KEYWORDS = {
    'rice':      ['rice', 'paddy', 'dhan', 'chawal', 'oryza', 'dhaan'],
    'wheat':     ['wheat', 'gehu', 'gehun', 'triticum', 'atta'],
    'tomato':    ['tomato', 'tamatar', 'tamato', 'lycopersicum'],
    'cotton':    ['cotton', 'kapas', 'kapaa', 'rui', 'gossypium'],
    'maize':     ['maize', 'corn', 'makka', 'makkai', 'bhutta'],
    'sugarcane': ['sugarcane', 'ganna', 'sugar cane', 'ikh', 'ikhh'],
    'soybean':   ['soybean', 'soya', 'soy', 'glycine'],
    'groundnut': ['groundnut', 'peanut', 'moongphali', 'mungfali'],
    'chilli':    ['chilli', 'chili', 'mirchi', 'pepper', 'mirch'],
    'onion':     ['onion', 'pyaz', 'kanda', 'pyaaz'],
}

STRESS_VOCABULARY = {
    'NUTRIENT_DEFICIENCY': [
        'yellow', 'yellowing', 'pale', 'light green', 'chlorosis', 'deficiency',
        'nutrient', 'nitrogen', 'phosphorus', 'potassium', 'stunted', 'slow growth',
        'discolor', 'discoloration', 'fading', 'whitish', 'interveinal', 'color loss'
    ],
    'FUNGAL_DISEASE': [
        'white powder', 'powdery mildew', 'brown spot', 'rust', 'blight',
        'mold', 'mould', 'fungus', 'lesion', 'spot', 'blotch', 'canker',
        'blast', 'smut', 'downy mildew', 'anthracnose', 'botrytis', 'gray mold',
        'dark spots', 'circular spots', 'ring spots'
    ],
    'WATER_STRESS': [
        'drying', 'dry', 'wilting', 'wilt', 'drooping', 'droop', 'dehydrated',
        'drought', 'crispy', 'brown tips', 'scorched', 'no water', 'thirsty',
        'shrivel', 'limp', 'dead', 'withered', 'wither'
    ],
    'PEST_INFESTATION': [
        'insect', 'pest', 'worm', 'caterpillar', 'aphid', 'whitefly', 'bug',
        'holes', 'eaten', 'larvae', 'grub', 'mite', 'thrips', 'mealy bug',
        'borer', 'grasshopper', 'locust', 'weevil', 'leaf miner', 'sucking'
    ],
    'VIRAL_DISEASE': [
        'mosaic', 'curling', 'curl', 'distorted', 'distortion', 'virus',
        'mottled', 'streaks', 'ring spot', 'vein clearing', 'necrosis',
        'leaf curl', 'yellowing mosaic', 'twisted', 'deformed'
    ],
    'BACTERIAL_DISEASE': [
        'bacterial', 'water soaked', 'ooze', 'soft rot', 'wet rot',
        'slime', 'smell', 'decay', 'canker', 'gall', 'angular spots',
        'greasy', 'oily spots', 'wilting sudden', 'fire blight'
    ],
    'HEAT_STRESS': [
        'scorching', 'sunburn', 'bleaching', 'heat', 'hot', 'burnt edges',
        'tip burn', 'sun scald', 'high temperature', 'sun damage', 'scorched edges'
    ],
    'WEED_INFESTATION': [
        'weed', 'weeds', 'wild grass', 'unwanted plants', 'wild plants',
        'grass', 'overgrown', 'crowded field', 'competition', 'kharpat',
        'khartpavar', 'full of weeds', 'weed problem', 'unwanted growth',
        'invasive', 'overgrowth'
    ]
}

AGRI_STOPWORDS = {
    'my', 'the', 'is', 'are', 'was', 'has', 'have', 'a', 'an', 'and', 'or',
    'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'this',
    'that', 'it', 'they', 'them', 'some', 'all', 'very', 'also', 'please',
    'can', 'you', 'tell', 'me', 'what', 'how', 'why', 'when', 'do', 'help',
    'problem', 'getting', 'found', 'noticed', 'see', 'look', 'looks',
    'crop', 'plant', 'field', 'farm', 'leaves', 'leaf', 'stem', 'root',
    'today', 'now', 'recently', 'bit', 'little', 'some', 'few', 'much'
}

# Words that by themselves give no crop stress signal
NOISE_WORDS = {'crop', 'plant', 'field', 'farm', 'hello', 'hi', 'test',
               'ok', 'okay', 'yes', 'no', 'maybe', 'check', 'see', 'look'}


class NLPProcessor:
    def __init__(self):
        self.lemmatizer = None
        self.stemmer = None
        self.stop_words = set()
        self._init_nlp()

    def _init_nlp(self):
        if NLTK_AVAILABLE:
            self.lemmatizer = WordNetLemmatizer()
            self.stemmer = PorterStemmer()
            try:
                self.stop_words = set(stopwords.words('english'))
            except Exception:
                self.stop_words = set()
        self.stop_words.update(AGRI_STOPWORDS)

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s\-]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def tokenize(self, text: str) -> List[str]:
        if NLTK_AVAILABLE:
            try:
                return word_tokenize(text)
            except Exception:
                pass
        return text.split()

    def remove_stopwords(self, tokens: List[str]) -> List[str]:
        return [t for t in tokens if t not in self.stop_words and len(t) > 2]

    def lemmatize(self, tokens: List[str]) -> List[str]:
        if self.lemmatizer:
            try:
                return [self.lemmatizer.lemmatize(token) for token in tokens]
            except Exception:
                pass
        if self.stemmer:
            try:
                return [self.stemmer.stem(token) for token in tokens]
            except Exception:
                pass
        return tokens

    def extract_bigrams(self, tokens: List[str]) -> List[str]:
        return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]

    def detect_crop(self, text: str) -> Tuple[str, float]:
        text_lower = text.lower()
        best_crop = "Unknown"
        best_score = 0.0
        for crop, keywords in CROP_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    score = len(kw) / 20.0
                    if score > best_score:
                        best_score = score
                        best_crop = crop.capitalize()
        return best_crop, min(best_score, 1.0)

    def extract_stress_features(self, tokens: List[str], original_text: str) -> Dict[str, float]:
        scores = {stress: 0.0 for stress in STRESS_VOCABULARY}
        text_lower = original_text.lower()

        for stress_type, keywords in STRESS_VOCABULARY.items():
            for kw in keywords:
                # Phrase match in full text (higher weight)
                if kw in text_lower:
                    scores[stress_type] += 2.0 if ' ' in kw else 1.5
                # Token match
                for token in tokens:
                    if kw == token:
                        scores[stress_type] += 1.0
                    elif len(kw) > 4 and kw[:5] == token[:5]:
                        scores[stress_type] += 0.4

        max_score = max(scores.values()) if max(scores.values()) > 0 else 1
        return {k: v / max_score for k, v in scores.items()}

    def _is_meaningful_query(self, tokens: List[str], original: str) -> bool:
        """
        Returns True if the query has any agricultural content.
        Only blocks completely empty/nonsensical queries.
        """
        # Block pure noise (hello, test, ok etc)
        meaningful = [t for t in tokens if t not in NOISE_WORDS and len(t) > 1]
        if len(meaningful) < 1:
            return False
        # If original query has at least 3 words, almost always meaningful
        words = original.strip().split()
        if len(words) >= 2:
            return True
        # Single word — only block if it's pure noise
        return len(meaningful) >= 1

    def process(self, query_text: str) -> Dict:
        if not query_text or len(query_text.strip()) < 2:
            return {
                'success': False,
                'error': 'Query too short',
                'original_text': query_text,
                'processed_tokens': [],
                'stress_features': {},
                'detected_crop': 'Unknown',
                'feature_vector': []
            }

        cleaned   = self.clean_text(query_text)
        tokens    = self.tokenize(cleaned)
        filtered  = self.remove_stopwords(tokens)
        lemmatized = self.lemmatize(filtered)
        bigrams   = self.extract_bigrams(lemmatized)

        # Check for meaningful content
        if not self._is_meaningful_query(lemmatized, query_text):
            return {
                'success': False,
                'error': 'insufficient_data',
                'original_text': query_text,
                'processed_tokens': lemmatized,
                'stress_features': {},
                'detected_crop': 'Unknown',
                'feature_vector': []
            }

        detected_crop, crop_confidence = self.detect_crop(query_text)
        stress_features = self.extract_stress_features(lemmatized + bigrams, query_text)

        all_stress_types = sorted(STRESS_VOCABULARY.keys())
        feature_vector   = [stress_features.get(st, 0.0) for st in all_stress_types]

        return {
            'success': True,
            'original_text': query_text,
            'cleaned_text': cleaned,
            'tokens': tokens,
            'filtered_tokens': filtered,
            'lemmatized_tokens': lemmatized,
            'bigrams': bigrams[:10],
            'detected_crop': detected_crop,
            'crop_confidence': crop_confidence,
            'stress_features': stress_features,
            'feature_vector': feature_vector,
            'stress_types_order': all_stress_types,
            'token_count': len(lemmatized),
            'unique_tokens': list(set(lemmatized))
        }


nlp_processor = NLPProcessor()
logger.info("✅ NLP Processor v2 initialized")
