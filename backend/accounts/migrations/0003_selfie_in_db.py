from django.db import migrations, models


class Migration(migrations.Migration):
    """Selfi diskdan bazaga ko'chiriladi (efemer disk muammosi — Render)."""

    dependencies = [
        ("accounts", "0002_user_selfie"),
    ]

    operations = [
        migrations.RemoveField(model_name="user", name="selfie"),
        migrations.AddField(
            model_name="user",
            name="selfie_data",
            field=models.BinaryField(
                blank=True, editable=False, null=True, verbose_name="Selfi (JPEG)"
            ),
        ),
    ]
