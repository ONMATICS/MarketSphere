from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group, Permission

from services.decorators.decorators import ADMIN_ROLE_PERMISSIONS


class Command(BaseCommand):
    help = "Create or synchronize MarketSphere administrative role groups."

    def handle(self, *args, **options):
        for role_name, permission_names in ADMIN_ROLE_PERMISSIONS.items():
            permissions = []
            for permission_name in permission_names:
                try:
                    app_label, codename = permission_name.split(".", 1)
                except ValueError as error:
                    raise CommandError(f"Invalid permission definition: {permission_name}") from error

                try:
                    permissions.append(
                        Permission.objects.get(
                            content_type__app_label=app_label,
                            codename=codename,
                        )
                    )
                except Permission.DoesNotExist as error:
                    raise CommandError(
                        f"Permission {permission_name!r} is unavailable; run migrations first."
                    ) from error

            group, created = Group.objects.get_or_create(name=role_name)
            group.permissions.set(permissions)
            action = "created" if created else "synchronized"
            self.stdout.write(f"{role_name}: {action} ({len(permissions)} permissions)")
