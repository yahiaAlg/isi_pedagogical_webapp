from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Comptes utilisateurs"

    def ready(self):
        # Wire up the UserProfile auto-create/repair signals
        import accounts.signals  # noqa: F401
