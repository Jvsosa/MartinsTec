from django.apps import AppConfig


class SitesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sites'

    def ready(self):
        try:
            from django.template.context import BaseContext
            from copy import copy

            def base_context_copy(self):
                duplicate = object.__new__(self.__class__)
                duplicate.__dict__.update(self.__dict__)
                duplicate.dicts = self.dicts[:]
                return duplicate

            BaseContext.__copy__ = base_context_copy
        except ImportError:
            pass

