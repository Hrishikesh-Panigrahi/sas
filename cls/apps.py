from django.apps import AppConfig


class ClsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cls'

    def ready(self):
        import cls.signals
   