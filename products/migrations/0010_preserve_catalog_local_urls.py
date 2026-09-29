from django.db import migrations


def preserve_existing_catalog_urls(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    Brand = apps.get_model("products", "Brand")

    for category in Category.objects.all().iterator():
        value = str(category.image or "")
        if value and not value.startswith(("http://", "https://", "/")):
            Category.objects.filter(pk=category.pk).update(
                image=f"/media/{value}"
            )

    for brand in Brand.objects.all().iterator():
        updates = {}
        for field_name in ("logo", "cover_image"):
            value = str(getattr(brand, field_name) or "")
            if value and not value.startswith(("http://", "https://", "/")):
                updates[field_name] = f"/media/{value}"
        if updates:
            Brand.objects.filter(pk=brand.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0009_productimage_media_type_alter_productimage_image"),
    ]

    operations = [
        migrations.RunPython(
            preserve_existing_catalog_urls,
            migrations.RunPython.noop,
        ),
    ]
