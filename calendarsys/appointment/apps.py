from django.apps import AppConfig


class AppointmentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "appointment"

    def ready(self):
        """
        Automatically create the Business Staff group and assign permissions.
        All imports MUST be inside ready(), otherwise Django throws
        AppRegistryNotReady.
        """
        try:
            from django.contrib.auth.models import Group, Permission
            from django.contrib.contenttypes.models import ContentType
            from .models import TimeSlot  # models imported here to avoid registry issues

            # Create or get the group
            group, created = Group.objects.get_or_create(name="Business Staff")

            # Assign only TimeSlot permissions
            ct = ContentType.objects.get_for_model(TimeSlot)
            perms = Permission.objects.filter(content_type=ct)

            group.permissions.set(perms)

        except Exception as e:
            # Do NOT crash migrations or server startup
            print("⚠ AppointmentConfig.ready() warning:", e)
