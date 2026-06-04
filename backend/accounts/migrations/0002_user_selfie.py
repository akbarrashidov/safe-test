from django.db import migrations, models

import accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="selfie",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=accounts.models.selfie_upload_path,
                verbose_name="Selfi",
            ),
        ),
    ]
