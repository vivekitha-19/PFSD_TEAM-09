"""
MongoDB Connector v2 — Farmer Advisory System
Includes: delete, clear history, multilingual fields, real stats
"""
import logging
from datetime import datetime
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from django.conf import settings
from bson import ObjectId

logger = logging.getLogger(__name__)

_client = None
_db = None


def get_db_connection():
    global _client, _db
    if _client is None:
        try:
            _client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            _client.admin.command('ping')
            _db = _client[settings.MONGODB_DB_NAME]
            logger.info("✅ MongoDB connected successfully")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"⚠️  MongoDB not available: {e}. Using in-memory fallback.")
            _client = None
            _db = None
    return _db


class FarmerAdvisoryDB:

    def __init__(self):
        self.db = get_db_connection()
        self._memory_store = {
            'crops': self._get_default_crops(),
            'stress_conditions': self._get_default_stress_conditions(),
            'advisory_data': self._get_default_advisory_data(),
            'farmer_queries': []
        }
        self._mem_id_counter = 0

    def _get_collection(self, name):
        if self.db is not None:
            return self.db[name]
        return None

    # ─── CROPS ────────────────────────────────────────────────────────────────

    def get_all_crops(self):
        col = self._get_collection('crops')
        if col is not None:
            try:
                return list(col.find({}, {'_id': 0}))
            except Exception as e:
                logger.error(f"DB error: {e}")
        return self._memory_store['crops']

    def get_crop_by_name(self, name):
        col = self._get_collection('crops')
        if col is not None:
            try:
                return col.find_one({'name': {'$regex': name, '$options': 'i'}}, {'_id': 0})
            except Exception as e:
                logger.error(f"DB error: {e}")
        for c in self._memory_store['crops']:
            if name.lower() in c['name'].lower():
                return c
        return None

    # ─── STRESS ───────────────────────────────────────────────────────────────

    def get_all_stress_conditions(self):
        col = self._get_collection('stress_conditions')
        if col is not None:
            try:
                return list(col.find({}, {'_id': 0}))
            except Exception as e:
                logger.error(f"DB error: {e}")
        return self._memory_store['stress_conditions']

    def get_stress_by_type(self, stress_type):
        col = self._get_collection('stress_conditions')
        if col is not None:
            try:
                return col.find_one({'stress_type': stress_type}, {'_id': 0})
            except Exception as e:
                logger.error(f"DB error: {e}")
        for s in self._memory_store['stress_conditions']:
            if s['stress_type'] == stress_type:
                return s
        return None

    # ─── ADVISORY ─────────────────────────────────────────────────────────────

    def get_advisory(self, stress_type, crop_name=None):
        col = self._get_collection('advisory_data')
        if col is not None:
            try:
                if crop_name:
                    result = col.find_one(
                        {'stress_type': stress_type, 'crop': {'$regex': crop_name, '$options': 'i'}},
                        {'_id': 0}
                    )
                    if result:
                        return result
                result = col.find_one({'stress_type': stress_type}, {'_id': 0})
                return result
            except Exception as e:
                logger.error(f"DB error: {e}")
        for adv in self._memory_store['advisory_data']:
            if adv['stress_type'] == stress_type:
                return adv
        return None

    def get_all_advisory(self):
        col = self._get_collection('advisory_data')
        if col is not None:
            try:
                return list(col.find({}, {'_id': 0}))
            except Exception as e:
                logger.error(f"DB error: {e}")
        return self._memory_store['advisory_data']

    # ─── QUERY HISTORY ────────────────────────────────────────────────────────

    def save_farmer_query(self, query_text, detected_stress, crop_detected,
                          confidence_score, advisory_provided,
                          farmer_id="anonymous", original_query=None,
                          input_language='en', selected_crop='', ai_source=''):
        """Save a processed farmer query to MongoDB with full metadata"""
        record = {
            'farmer_id':        farmer_id,
            'query_text':       query_text,
            'original_query':   original_query or query_text,
            'detected_stress':  detected_stress,
            'crop_detected':    crop_detected,
            'selected_crop':    selected_crop or '',
            'confidence_score': round(float(confidence_score), 4),
            'advisory_provided':advisory_provided,
            'input_language':   input_language,
            'ai_source':        ai_source or '',
            'timestamp':        datetime.utcnow().isoformat(),
        }
        col = self._get_collection('farmer_queries')
        if col is not None:
            try:
                result = col.insert_one(dict(record))
                record['_id'] = str(result.inserted_id)
                record['id']  = str(result.inserted_id)
                logger.info(f"✅ Query saved to MongoDB: {record['_id']}")
                return record
            except Exception as e:
                logger.error(f"DB save error: {e}")

        # In-memory fallback
        self._mem_id_counter += 1
        record['_id'] = f"mem_{self._mem_id_counter}"
        record['id']  = record['_id']
        self._memory_store['farmer_queries'].append(record)
        return record

    def get_query_history(self, farmer_id=None, limit=50):
        """Get query history, newest first"""
        col = self._get_collection('farmer_queries')
        if col is not None:
            try:
                query = {}
                if farmer_id:
                    query['farmer_id'] = farmer_id
                results = list(
                    col.find(query).sort('timestamp', DESCENDING).limit(limit)
                )
                # Convert ObjectId to string
                for r in results:
                    r['_id'] = str(r['_id'])
                    r['id']  = r['_id']
                return results
            except Exception as e:
                logger.error(f"DB history error: {e}")

        history = list(reversed(self._memory_store['farmer_queries']))
        if farmer_id:
            history = [q for q in history if q.get('farmer_id') == farmer_id]
        return history[:limit]

    def delete_query(self, record_id: str, farmer_id: str = None) -> bool:
        """Delete a single query record by ID"""
        col = self._get_collection('farmer_queries')
        if col is not None:
            try:
                query = {}
                # Try ObjectId first, then string _id
                try:
                    query['_id'] = ObjectId(record_id)
                except Exception:
                    query['_id'] = record_id
                if farmer_id:
                    query['farmer_id'] = farmer_id
                result = col.delete_one(query)
                logger.info(f"Deleted query {record_id}: {result.deleted_count} records")
                return result.deleted_count > 0
            except Exception as e:
                logger.error(f"DB delete error: {e}")
                return False

        # In-memory fallback
        before = len(self._memory_store['farmer_queries'])
        self._memory_store['farmer_queries'] = [
            q for q in self._memory_store['farmer_queries']
            if q.get('_id') != record_id
        ]
        return len(self._memory_store['farmer_queries']) < before

    def clear_history(self, farmer_id: str = None) -> int:
        """Clear all query history for a farmer (or all if no farmer_id)"""
        col = self._get_collection('farmer_queries')
        if col is not None:
            try:
                query = {'farmer_id': farmer_id} if farmer_id else {}
                result = col.delete_many(query)
                logger.info(f"Cleared {result.deleted_count} queries")
                return result.deleted_count
            except Exception as e:
                logger.error(f"DB clear error: {e}")
                return 0

        before = len(self._memory_store['farmer_queries'])
        if farmer_id:
            self._memory_store['farmer_queries'] = [
                q for q in self._memory_store['farmer_queries']
                if q.get('farmer_id') != farmer_id
            ]
        else:
            self._memory_store['farmer_queries'] = []
        return before - len(self._memory_store['farmer_queries'])

    # ─── DB INIT / SEEDING ───────────────────────────────────────────────────

    def initialize_collections(self):
        if self.db is None:
            logger.info("Using in-memory storage — MongoDB not available")
            return
        if self.db['crops'].count_documents({}) == 0:
            self.db['crops'].insert_many(self._get_default_crops())
            logger.info("✅ Seeded crops")
        if self.db['stress_conditions'].count_documents({}) == 0:
            self.db['stress_conditions'].insert_many(self._get_default_stress_conditions())
            logger.info("✅ Seeded stress_conditions")
        if self.db['advisory_data'].count_documents({}) == 0:
            self.db['advisory_data'].insert_many(self._get_default_advisory_data())
            logger.info("✅ Seeded advisory_data")

    # ─── DEFAULT DATA ─────────────────────────────────────────────────────────

    def _get_default_crops(self):
        return [
            {"name": "Rice", "scientific_name": "Oryza sativa", "season": "Kharif",
             "common_diseases": ["Blast", "Brown Spot", "Leaf Folder", "Yellow Leaf Curl"],
             "soil_type": "Clayey", "water_requirement": "High"},
            {"name": "Wheat", "scientific_name": "Triticum aestivum", "season": "Rabi",
             "common_diseases": ["Rust", "Smut", "Powdery Mildew", "Karnal Bunt"],
             "soil_type": "Loamy", "water_requirement": "Medium"},
            {"name": "Tomato", "scientific_name": "Solanum lycopersicum", "season": "Rabi/Kharif",
             "common_diseases": ["Early Blight", "Late Blight", "Powdery Mildew", "Leaf Curl"],
             "soil_type": "Sandy Loam", "water_requirement": "Medium"},
            {"name": "Cotton", "scientific_name": "Gossypium hirsutum", "season": "Kharif",
             "common_diseases": ["Bollworm", "Leaf Curl Virus", "Root Rot", "Wilt"],
             "soil_type": "Black Cotton Soil", "water_requirement": "Medium"},
            {"name": "Maize", "scientific_name": "Zea mays", "season": "Kharif",
             "common_diseases": ["Downy Mildew", "Stalk Rot", "Leaf Blight", "Smut"],
             "soil_type": "Sandy Loam", "water_requirement": "Medium"},
            {"name": "Sugarcane", "scientific_name": "Saccharum officinarum", "season": "Annual",
             "common_diseases": ["Red Rot", "Wilt", "Smut", "Grassy Shoot"],
             "soil_type": "Loamy", "water_requirement": "High"},
            {"name": "Soybean", "scientific_name": "Glycine max", "season": "Kharif",
             "common_diseases": ["Rust", "Root Rot", "Pod Borer", "Bacterial Pustule"],
             "soil_type": "Well-drained", "water_requirement": "Low"},
            {"name": "Groundnut", "scientific_name": "Arachis hypogaea", "season": "Kharif",
             "common_diseases": ["Tikka", "Root Rot", "Collar Rot", "Bud Necrosis"],
             "soil_type": "Sandy", "water_requirement": "Low"},
        ]

    def _get_default_stress_conditions(self):
        return [
            {"stress_type": "NUTRIENT_DEFICIENCY", "display_name": "Nutrient Deficiency",
             "symptoms": ["yellowing leaves","pale color","stunted growth","yellow","pale","light green"],
             "severity": "Medium", "category": "Abiotic",
             "description": "Lack of essential nutrients causing visible leaf symptoms"},
            {"stress_type": "FUNGAL_DISEASE", "display_name": "Fungal Disease",
             "symptoms": ["white powder","brown spots","rust","mildew","blight","mold"],
             "severity": "High", "category": "Biotic",
             "description": "Fungal pathogens causing visible lesions and powder-like growth"},
            {"stress_type": "WATER_STRESS", "display_name": "Water/Drought Stress",
             "symptoms": ["drying","wilting","drooping","dry","brown tips","crispy","wilt"],
             "severity": "High", "category": "Abiotic",
             "description": "Insufficient water supply causing wilting and drying"},
            {"stress_type": "PEST_INFESTATION", "display_name": "Pest Infestation",
             "symptoms": ["holes in leaves","insects","worms","caterpillar","aphids","bugs"],
             "severity": "High", "category": "Biotic",
             "description": "Attack by insects or pests causing physical damage"},
            {"stress_type": "VIRAL_DISEASE", "display_name": "Viral Disease",
             "symptoms": ["mosaic pattern","curling","distorted","curl","mosaic","stunted"],
             "severity": "Very High", "category": "Biotic",
             "description": "Viral pathogens causing mosaic patterns and leaf distortion"},
            {"stress_type": "BACTERIAL_DISEASE", "display_name": "Bacterial Disease",
             "symptoms": ["water soaked","ooze","canker","bacterial","wet rot","soft rot"],
             "severity": "High", "category": "Biotic",
             "description": "Bacterial infection causing water-soaked lesions and rot"},
            {"stress_type": "HEAT_STRESS", "display_name": "Heat Stress",
             "symptoms": ["scorching","sunburn","bleaching","heat","burnt","scorched"],
             "severity": "Medium", "category": "Abiotic",
             "description": "High temperature damage causing leaf scorching and bleaching"},
            {"stress_type": "WEED_INFESTATION", "display_name": "Weed Infestation",
             "symptoms": ["weed","weeds","kharpatch","kharpat","khartpavar","unwanted plants",
                          "grass","wild plants","competition","crowded"],
             "severity": "Medium", "category": "Abiotic",
             "description": "Unwanted plants competing for nutrients, water, and sunlight"},
        ]

    def _get_default_advisory_data(self):
        return [
            {
                "stress_type": "NUTRIENT_DEFICIENCY", "crop": "General",
                "title": "Nutrient Deficiency Treatment",
                "immediate_action": "Apply balanced NPK fertilizer immediately",
                "treatment": [
                    "Apply Urea @ 25 kg/acre for nitrogen deficiency (yellowing leaves)",
                    "Apply DAP (Di-Ammonium Phosphate) @ 20 kg/acre for phosphorus deficiency",
                    "Apply Muriate of Potash (MOP) @ 15 kg/acre for potassium deficiency",
                    "Spray 1% Urea solution as foliar spray for quick recovery",
                    "Apply micronutrient mixture containing Zinc, Boron, and Magnesium"
                ],
                "prevention": [
                    "Conduct soil testing before each crop season",
                    "Follow recommended fertilizer schedule for your crop",
                    "Use organic manure to improve soil nutrient retention",
                    "Maintain proper soil pH (6.0-7.0) for nutrient availability"
                ],
                "fertilizers": ["Urea","DAP","MOP","Zinc Sulfate","Boron","Micronutrient Mix"],
                "follow_up": "Monitor crop for 7-10 days after treatment. Repeat foliar spray if needed.",
                "severity_level": "Medium"
            },
            {
                "stress_type": "FUNGAL_DISEASE", "crop": "General",
                "title": "Fungal Disease Control",
                "immediate_action": "Apply systemic fungicide within 24 hours",
                "treatment": [
                    "Spray Mancozeb 75% WP @ 2.5 g/liter of water",
                    "Apply Carbendazim 50% WP @ 1 g/liter for powdery mildew",
                    "Use Propiconazole 25% EC @ 1 ml/liter for rust diseases",
                    "Remove and destroy severely infected plant parts",
                    "Ensure proper ventilation and spacing between plants"
                ],
                "prevention": [
                    "Use disease-resistant varieties",
                    "Avoid overhead irrigation; use drip irrigation",
                    "Apply preventive fungicide during humid conditions",
                    "Rotate crops every season to break disease cycle"
                ],
                "fertilizers": ["Mancozeb","Carbendazim","Propiconazole","Copper Hydroxide"],
                "follow_up": "Re-spray after 7-10 days. Repeat 2-3 times for complete control.",
                "severity_level": "High"
            },
            {
                "stress_type": "WATER_STRESS", "crop": "General",
                "title": "Water/Drought Stress Management",
                "immediate_action": "Irrigate immediately with 3-4 cm of water",
                "treatment": [
                    "Provide immediate irrigation — 4-5 cm water for field crops",
                    "Apply mulching with dry leaves or straw to retain soil moisture",
                    "Spray Kaolin clay (5%) to reduce transpiration",
                    "Apply Potassium Nitrate (0.5%) as foliar spray to improve drought tolerance",
                    "Reduce plant density by thinning overcrowded plants if needed"
                ],
                "prevention": [
                    "Install drip irrigation for efficient water use",
                    "Mulch the field to conserve soil moisture",
                    "Plant drought-tolerant varieties in water-scarce regions",
                    "Schedule irrigation based on crop water requirement chart"
                ],
                "fertilizers": ["Potassium Nitrate","Seaweed Extract","Humic Acid"],
                "follow_up": "Monitor soil moisture daily. Irrigate at critical crop growth stages.",
                "severity_level": "High"
            },
            {
                "stress_type": "PEST_INFESTATION", "crop": "General",
                "title": "Pest Infestation Control",
                "immediate_action": "Apply recommended pesticide immediately to stop spread",
                "treatment": [
                    "Spray Chlorpyrifos 20% EC @ 2 ml/liter for sucking pests",
                    "Apply Emamectin Benzoate 5% SG @ 0.5 g/liter for caterpillars/worms",
                    "Use Neem-based pesticide (NSKE 5%) as eco-friendly option",
                    "Install yellow sticky traps @ 10/acre for whiteflies and aphids",
                    "Release natural predators like ladybird beetles for biological control"
                ],
                "prevention": [
                    "Monitor field regularly using sticky traps",
                    "Practice crop rotation to break pest cycles",
                    "Use pheromone traps for monitoring moth populations",
                    "Plant border crops like marigold to trap pests"
                ],
                "fertilizers": ["Neem Oil","Chlorpyrifos","Emamectin Benzoate"],
                "follow_up": "Inspect field after 5 days. Repeat spray if pest population persists.",
                "severity_level": "High"
            },
            {
                "stress_type": "VIRAL_DISEASE", "crop": "General",
                "title": "Viral Disease Management",
                "immediate_action": "Remove infected plants and control vector insects immediately",
                "treatment": [
                    "Remove and burn all infected plants to prevent spread",
                    "Control vector insects (whiteflies/aphids) with Imidacloprid @ 0.3 ml/liter",
                    "Spray mineral oil (1%) to reduce virus spread by aphids",
                    "Apply reflective mulch to repel vector insects",
                    "No direct cure exists — focus on preventing spread to healthy plants"
                ],
                "prevention": [
                    "Use virus-resistant/tolerant crop varieties",
                    "Control whiteflies and aphids with systemic insecticides",
                    "Remove infected plants early before virus spreads",
                    "Maintain 45-day crop-free period to break virus cycle"
                ],
                "fertilizers": ["Imidacloprid","Mineral Oil Spray","Copper Fungicide"],
                "follow_up": "No chemical cure. Uprooting all infected plants is mandatory.",
                "severity_level": "Very High"
            },
            {
                "stress_type": "BACTERIAL_DISEASE", "crop": "General",
                "title": "Bacterial Disease Treatment",
                "immediate_action": "Apply copper-based bactericide immediately",
                "treatment": [
                    "Spray Copper Hydroxide 77% WP @ 3 g/liter of water",
                    "Apply Streptocycline @ 0.5 g/liter + Copper Oxychloride @ 2.5 g/liter",
                    "Remove infected plant parts and disinfect pruning tools",
                    "Avoid overhead irrigation that spreads bacterial splash",
                    "Apply lime to soil to reduce bacterial survival"
                ],
                "prevention": [
                    "Use certified disease-free seed and planting material",
                    "Avoid working in field when plants are wet",
                    "Practice crop rotation with non-host crops",
                    "Disinfect farm tools regularly with bleach solution"
                ],
                "fertilizers": ["Copper Hydroxide","Streptocycline","Bordeaux Mixture"],
                "follow_up": "Apply bactericide spray 2-3 times at 7-day intervals.",
                "severity_level": "High"
            },
            {
                "stress_type": "HEAT_STRESS", "crop": "General",
                "title": "Heat Stress Management",
                "immediate_action": "Irrigate immediately and provide shade if possible",
                "treatment": [
                    "Irrigate field immediately — evening irrigation preferred",
                    "Apply Kaolin clay spray (5%) to reduce leaf surface temperature",
                    "Spray Salicylic acid (100 ppm) to improve heat tolerance",
                    "Apply shade nets (35-50% shade) for high-value crops",
                    "Reduce nitrogen application during heat stress period"
                ],
                "prevention": [
                    "Select heat-tolerant crop varieties for hot regions",
                    "Schedule planting to avoid peak summer temperatures",
                    "Use mulching to maintain cool root zone temperature",
                    "Irrigate in evening to cool plant canopy"
                ],
                "fertilizers": ["Potassium Sulfate","Salicylic Acid","Calcium Nitrate"],
                "follow_up": "Continue irrigation every 3-4 days during heat wave.",
                "severity_level": "Medium"
            },
            {
                "stress_type": "WEED_INFESTATION", "crop": "General",
                "title": "Weed Infestation Management",
                "immediate_action": "Begin manual weeding or apply pre-emergent herbicide immediately",
                "treatment": [
                    "Manual weeding within first 15-21 days after sowing (critical weed-free period)",
                    "Apply Pendimethalin 30% EC @ 3.3 liter/hectare as pre-emergent herbicide",
                    "For rice: apply Bispyribac-sodium 10% SC @ 200 ml/hectare at 15-20 DAS",
                    "Use inter-cultivation with tractor-mounted cultivator to uproot weeds",
                    "Apply Atrazine 50% WP @ 1.5 kg/hectare for maize (post-emergence)"
                ],
                "prevention": [
                    "Use certified weed-free seed to reduce weed seed bank",
                    "Maintain proper crop spacing — dense canopy suppresses weeds",
                    "Apply thick organic mulch (4-6 cm) to prevent weed germination",
                    "Practice crop rotation as different crops allow different weed control methods",
                    "Use stale seedbed technique — prepare field, allow weeds to germinate, then destroy"
                ],
                "fertilizers": ["Pendimethalin","Bispyribac-sodium","Atrazine","Glyphosate (non-crop areas only)"],
                "follow_up": "Re-inspect field every 10 days. A second weeding may be needed at 35-40 DAS.",
                "severity_level": "Medium"
            },
        ]


db_instance = FarmerAdvisoryDB()
