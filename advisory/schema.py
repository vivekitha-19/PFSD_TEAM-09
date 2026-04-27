"""
GraphQL Schema v6 — FarmAI
FIXES:
  - NLP failure NEVER blocks the pipeline — always falls through to AI
  - Advisory ALWAYS generated — no "Not Enough Information" for real queries
  - Delete mutation fixed
  - All fields consistent with frontend expectations
"""
import graphene
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


# ─── Types ─────────────────────────────────────────────────────────────────────

class CropType(graphene.ObjectType):
    name              = graphene.String()
    scientific_name   = graphene.String()
    season            = graphene.String()
    common_diseases   = graphene.List(graphene.String)
    soil_type         = graphene.String()
    water_requirement = graphene.String()


class StressConditionType(graphene.ObjectType):
    stress_type  = graphene.String()
    display_name = graphene.String()
    symptoms     = graphene.List(graphene.String)
    severity     = graphene.String()
    category     = graphene.String()
    description  = graphene.String()


class AdvisoryType(graphene.ObjectType):
    stress_type        = graphene.String()
    crop               = graphene.String()
    title              = graphene.String()
    immediate_action   = graphene.String()
    treatment          = graphene.List(graphene.String)
    prevention         = graphene.List(graphene.String)
    fertilizers        = graphene.List(graphene.String)
    follow_up          = graphene.String()
    severity_level     = graphene.String()
    ai_insight         = graphene.String()
    translated_to      = graphene.String()
    translated_to_name = graphene.String()
    source             = graphene.String()


class TranslationInfoType(graphene.ObjectType):
    original_text    = graphene.String()
    translated_text  = graphene.String()
    source_lang      = graphene.String()
    source_lang_name = graphene.String()
    was_translated   = graphene.Boolean()
    target_lang      = graphene.String()


class NLPResultType(graphene.ObjectType):
    original_text   = graphene.String()
    cleaned_text    = graphene.String()
    detected_crop   = graphene.String()
    crop_confidence = graphene.Float()
    filtered_tokens = graphene.List(graphene.String)
    bigrams         = graphene.List(graphene.String)
    token_count     = graphene.Int()
    input_language  = graphene.String()
    input_lang_name = graphene.String()


class ClassificationResultType(graphene.ObjectType):
    predicted_stress   = graphene.String()
    display_name       = graphene.String()
    confidence         = graphene.Float()
    confidence_percent = graphene.String()
    severity           = graphene.String()
    color              = graphene.String()
    model_used         = graphene.String()
    insufficient_data  = graphene.Boolean()


class QueryResponseType(graphene.ObjectType):
    success          = graphene.Boolean()
    query_text       = graphene.String()
    timestamp        = graphene.String()
    nlp_result       = graphene.Field(NLPResultType)
    ml_result        = graphene.Field(ClassificationResultType)
    advisory         = graphene.Field(AdvisoryType)
    translation_info = graphene.Field(TranslationInfoType)
    error_message    = graphene.String()


class QueryHistoryType(graphene.ObjectType):
    id               = graphene.String()
    farmer_id        = graphene.String()
    query_text       = graphene.String()
    original_query   = graphene.String()
    input_language   = graphene.String()
    detected_stress  = graphene.String()
    crop_detected    = graphene.String()
    confidence_score = graphene.Float()
    advisory_provided = graphene.String()
    timestamp        = graphene.String()
    ai_source        = graphene.String()


class SystemStatsType(graphene.ObjectType):
    total_crops         = graphene.Int()
    total_stress_types  = graphene.Int()
    total_queries       = graphene.Int()
    queries_today       = graphene.Int()
    model_accuracy      = graphene.String()
    db_status           = graphene.String()
    db_type             = graphene.String()
    system_version      = graphene.String()
    supported_languages = graphene.Int()
    ai_engine_status    = graphene.String()


class DeleteResultType(graphene.ObjectType):
    success    = graphene.Boolean()
    message    = graphene.String()
    deleted_id = graphene.String()


# ─── Queries ───────────────────────────────────────────────────────────────────

class Query(graphene.ObjectType):
    all_crops             = graphene.List(CropType)
    crop_by_name          = graphene.Field(CropType, name=graphene.String(required=True))
    all_stress_conditions = graphene.List(StressConditionType)
    stress_by_type        = graphene.Field(StressConditionType, stress_type=graphene.String(required=True))
    query_history         = graphene.List(
        QueryHistoryType,
        farmer_id=graphene.String(),
        limit=graphene.Int(default_value=50)
    )
    system_stats  = graphene.Field(SystemStatsType)
    system_status = graphene.String()

    def resolve_all_crops(self, info):
        from db_connector import db_instance
        return [CropType(**{k: v for k, v in c.items() if k != '_id'})
                for c in db_instance.get_all_crops()]

    def resolve_crop_by_name(self, info, name):
        from db_connector import db_instance
        c = db_instance.get_crop_by_name(name)
        return CropType(**{k: v for k, v in c.items() if k != '_id'}) if c else None

    def resolve_all_stress_conditions(self, info):
        from db_connector import db_instance
        return [StressConditionType(**{k: v for k, v in s.items() if k != '_id'})
                for s in db_instance.get_all_stress_conditions()]

    def resolve_stress_by_type(self, info, stress_type):
        from db_connector import db_instance
        s = db_instance.get_stress_by_type(stress_type)
        return StressConditionType(**{k: v for k, v in s.items() if k != '_id'}) if s else None

    def resolve_query_history(self, info, farmer_id=None, limit=50):
        from db_connector import db_instance
        history = db_instance.get_query_history(farmer_id=farmer_id, limit=limit)
        results = []
        for h in history:
            results.append(QueryHistoryType(
                id                = str(h.get('_id', h.get('id', ''))),
                farmer_id         = h.get('farmer_id', 'anonymous'),
                query_text        = h.get('query_text', ''),
                original_query    = h.get('original_query', h.get('query_text', '')),
                input_language    = h.get('input_language', 'en'),
                detected_stress   = h.get('detected_stress', ''),
                crop_detected     = h.get('crop_detected', ''),
                confidence_score  = h.get('confidence_score', 0.0),
                advisory_provided = h.get('advisory_provided', ''),
                timestamp         = h.get('timestamp', ''),
                ai_source         = h.get('ai_source', '')
            ))
        return results

    def resolve_system_stats(self, info):
        import os, json as _j
        from db_connector import db_instance
        crops    = db_instance.get_all_crops()
        stresses = db_instance.get_all_stress_conditions()
        history  = db_instance.get_query_history(limit=10000)
        today    = date.today().isoformat()
        today_qs = sum(1 for q in history if q.get('timestamp', '').startswith(today))

        hf_ok = bool(os.environ.get('HUGGINGFACE_API_KEY'))
        oa_ok = bool(os.environ.get('OPENAI_API_KEY') and
                     not os.environ.get('OPENAI_API_KEY', '').startswith('sk-placeholder'))
        ai_status = ('OpenAI+HuggingFace' if oa_ok and hf_ok
                     else 'HuggingFace BERT' if hf_ok
                     else 'CSV-trained TF-IDF')

        model_info_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'ml_model', 'model_info.json'
        )
        acc_str = 'N/A'
        try:
            real_path = os.path.normpath(model_info_path)
            if os.path.exists(real_path):
                with open(real_path) as f:
                    mi = _j.load(f)
                acc_str = f"{mi.get('accuracy', 0)*100:.1f}%"
        except Exception:
            pass

        return SystemStatsType(
            total_crops         = len(crops),
            total_stress_types  = len(stresses),
            total_queries       = len(history),
            queries_today       = today_qs,
            model_accuracy      = acc_str,
            db_status           = 'connected' if db_instance.db is not None else 'in-memory',
            db_type             = 'MongoDB Atlas' if db_instance.db is not None else 'In-Memory',
            system_version      = '6.0.0',
            supported_languages = 9,
            ai_engine_status    = ai_status
        )

    def resolve_system_status(self, info):
        from db_connector import db_instance
        return f"FarmAI v6.0 | DB: {'MongoDB Atlas' if db_instance.db is not None else 'In-Memory'} | AI Active"


# ─── Mutations ─────────────────────────────────────────────────────────────────

class SubmitFarmerQuery(graphene.Mutation):
    """
    Core mutation — ALWAYS produces an advisory.
    NLP failure is handled gracefully (uses raw text for AI).
    Advisory generation never blocked by confidence thresholds.
    """
    class Arguments:
        query_text    = graphene.String(required=True)
        farmer_id     = graphene.String(default_value='anonymous')
        input_lang    = graphene.String(default_value='auto')
        selected_crop = graphene.String(default_value='')

    Output = QueryResponseType

    def mutate(self, info, query_text, farmer_id='anonymous',
               input_lang='auto', selected_crop=''):
        try:
            from nlp_engine import (nlp_processor, translate_to_english,
                                    translate_advisory_to_language,
                                    translate_text_to_language, LANG_NAMES)
            from ai_engine import ai_engine
            from db_connector import db_instance

            # Always use the session email as the authoritative farmer_id.
            # The client-supplied farmer_id is only a fallback when not logged in.
            request = info.context
            session_email = getattr(request, 'session', {}).get('user_email', '')
            if session_email:
                farmer_id = session_email

            ts = datetime.utcnow().isoformat()
            logger.info(f"Query: '{query_text[:60]}'")

            # ── Step 1: Translate to English ──────────────────────────────────
            try:
                trans        = translate_to_english(query_text, source_lang=input_lang)
                english_text = trans['translated']
                source_lang  = trans['source_lang']
            except Exception as e:
                logger.warning(f"Translation failed, using original: {e}")
                english_text = query_text
                source_lang  = 'en'
                trans = {'translated': query_text, 'source_lang': 'en',
                         'was_translated': False, 'source_lang_name': 'English'}

            translation_info = TranslationInfoType(
                original_text    = query_text,
                translated_text  = english_text,
                source_lang      = source_lang,
                source_lang_name = LANG_NAMES.get(source_lang, source_lang),
                was_translated   = trans.get('was_translated', False),
                target_lang      = source_lang
            )

            # ── Step 2: NLP (NEVER blocks — graceful degradation) ─────────────
            nlp_result    = {}
            detected_crop = ''
            feature_vector = []
            filtered_tokens = []
            token_count    = 0

            try:
                nlp_result     = nlp_processor.process(english_text)
                detected_crop  = nlp_result.get('detected_crop', 'Unknown')
                feature_vector = nlp_result.get('feature_vector', [])
                filtered_tokens = nlp_result.get('filtered_tokens', [])
                token_count    = nlp_result.get('token_count', 0)
            except Exception as e:
                logger.warning(f"NLP failed (non-blocking): {e}")

            # Override crop if user selected one in UI
            if selected_crop and selected_crop.strip().lower() not in ('', 'none', 'null', 'unknown'):
                detected_crop = selected_crop.strip().capitalize()

            # ── Step 3+4: AI Classification + Advisory (ALWAYS runs) ──────────
            ai_result = ai_engine.full_pipeline(
                english_query     = english_text,
                feature_vector    = feature_vector,
                selected_crop     = detected_crop,
                nlp_detected_crop = nlp_result.get('detected_crop', '') if nlp_result else ''
            )

            classification = ai_result['classification']
            advisory_data  = ai_result['advisory']
            stress_type    = classification.get('predicted_stress', 'FUNGAL_DISEASE')

            # ── Step 5: Translate advisory back to user language ──────────────
            try:
                if source_lang != 'en' and advisory_data:
                    advisory_data = translate_advisory_to_language(advisory_data, source_lang)

                display_name = classification.get('display_name', '')
                if source_lang != 'en' and display_name:
                    display_name = translate_text_to_language(display_name, source_lang)
                else:
                    display_name = classification.get('display_name', stress_type)
            except Exception as e:
                logger.warning(f"Translation of advisory failed: {e}")
                display_name = classification.get('display_name', stress_type)

            # ── Step 6: Save to MongoDB Atlas ─────────────────────────────────
            try:
                db_instance.save_farmer_query(
                    query_text        = english_text,
                    original_query    = query_text,
                    detected_stress   = stress_type,
                    crop_detected     = detected_crop or 'Unknown',
                    confidence_score  = classification.get('confidence', 0.5),
                    advisory_provided = advisory_data.get('title', '') if advisory_data else '',
                    farmer_id         = farmer_id,
                    input_language    = source_lang,
                    selected_crop     = selected_crop,
                    ai_source         = advisory_data.get('_source', '') if advisory_data else ''
                )
            except Exception as e:
                logger.warning(f"MongoDB save failed (non-blocking): {e}")

            # ── Build NLP response object ─────────────────────────────────────
            nlp_type = NLPResultType(
                original_text   = english_text,
                cleaned_text    = nlp_result.get('cleaned_text', english_text) if nlp_result else english_text,
                detected_crop   = detected_crop or 'Unknown',
                crop_confidence = nlp_result.get('crop_confidence', 0.0) if nlp_result else 0.0,
                filtered_tokens = filtered_tokens[:10],
                bigrams         = nlp_result.get('bigrams', [])[:5] if nlp_result else [],
                token_count     = token_count,
                input_language  = source_lang,
                input_lang_name = LANG_NAMES.get(source_lang, source_lang)
            )

            ml_type = ClassificationResultType(
                predicted_stress   = stress_type,
                display_name       = display_name,
                confidence         = classification.get('confidence', 0.5),
                confidence_percent = classification.get('confidence_percent', '50.0%'),
                severity           = classification.get('severity', 'Medium'),
                color              = classification.get('color', '#16a34a'),
                model_used         = classification.get('model_used', 'AI Engine'),
                insufficient_data  = False   # NEVER true — always show advisory
            )

            # Build advisory — always populated
            advisory_type = None
            if advisory_data:
                advisory_type = AdvisoryType(
                    stress_type        = advisory_data.get('stress_type', stress_type),
                    crop               = advisory_data.get('crop', detected_crop or 'General'),
                    title              = advisory_data.get('title', f'{stress_type.replace("_"," ").title()} Advisory'),
                    immediate_action   = advisory_data.get('immediate_action', 'Consult your nearest KVK for guidance.'),
                    treatment          = advisory_data.get('treatment', []),
                    prevention         = advisory_data.get('prevention', []),
                    fertilizers        = advisory_data.get('fertilizers', []),
                    follow_up          = advisory_data.get('follow_up', 'Monitor crop and follow up after 7 days.'),
                    severity_level     = advisory_data.get('severity_level', classification.get('severity', 'Medium')),
                    ai_insight         = advisory_data.get('ai_insight', ''),
                    translated_to      = advisory_data.get('_translated_to', 'en'),
                    translated_to_name = advisory_data.get('_translated_to_name', 'English'),
                    source             = advisory_data.get('_source', 'AI Advisory Engine')
                )

            return QueryResponseType(
                success=True, query_text=query_text, timestamp=ts,
                nlp_result=nlp_type, ml_result=ml_type,
                advisory=advisory_type, translation_info=translation_info,
                error_message=None
            )

        except Exception as e:
            logger.error(f"Mutation error: {e}", exc_info=True)
            return QueryResponseType(
                success=False, query_text=query_text,
                error_message=f"Server error: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )


class DeleteQueryRecord(graphene.Mutation):
    """Delete a single query from MongoDB by its ID"""
    class Arguments:
        record_id = graphene.String(required=True)
        farmer_id = graphene.String(default_value='anonymous')

    Output = DeleteResultType

    def mutate(self, info, record_id, farmer_id='anonymous'):
        try:
            from db_connector import db_instance
            logger.info(f"Deleting query: {record_id}")
            success = db_instance.delete_query(record_id)
            return DeleteResultType(
                success    = success,
                message    = 'Deleted successfully' if success else 'Record not found',
                deleted_id = record_id if success else None
            )
        except Exception as e:
            logger.error(f"Delete error: {e}")
            return DeleteResultType(success=False, message=str(e), deleted_id=None)


class ClearAllHistory(graphene.Mutation):
    """Clear all query history"""
    class Arguments:
        farmer_id = graphene.String(default_value='anonymous')

    Output = DeleteResultType

    def mutate(self, info, farmer_id='anonymous'):
        try:
            from db_connector import db_instance
            count = db_instance.clear_history(farmer_id)
            return DeleteResultType(
                success    = True,
                message    = f'{count} queries deleted',
                deleted_id = None
            )
        except Exception as e:
            return DeleteResultType(success=False, message=str(e), deleted_id=None)


class Mutation(graphene.ObjectType):
    submit_farmer_query = SubmitFarmerQuery.Field()
    delete_query_record = DeleteQueryRecord.Field()
    clear_all_history   = ClearAllHistory.Field()
