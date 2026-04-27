from django.apps import AppConfig


class AdvisoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'advisory'
    verbose_name = 'Farmer Advisory System'

    def ready(self):
        """Initialize system on startup"""
        try:
            from db_connector import db_instance
            db_instance.initialize_collections()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"DB init warning: {e}")
