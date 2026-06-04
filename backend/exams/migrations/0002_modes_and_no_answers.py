from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0001_initial"),
    ]

    operations = [
        # Javoblar endi bazada saqlanmaydi (Redis'da, TTL bilan)
        migrations.DeleteModel(name="Answer"),
        migrations.RemoveField(model_name="attempt", name="current_question"),
        migrations.AddField(
            model_name="attempt",
            name="mode",
            field=models.CharField(
                choices=[("exam", "Imtihon")],
                default="exam",
                max_length=16,
                verbose_name="Rejim",
            ),
        ),
        migrations.AddField(
            model_name="test",
            name="exam_question_count",
            field=models.PositiveIntegerField(
                default=25,
                help_text="Imtihonda har bo'limdan aralashtirib tanlanadigan savollar soni.",
                verbose_name="Imtihon savollari soni",
            ),
        ),
        migrations.AddField(
            model_name="test",
            name="block_size",
            field=models.PositiveIntegerField(
                default=25,
                help_text="Tayyorlanish rejimida bitta bo'limdagi savollar soni.",
                verbose_name="Bo'lim kattaligi",
            ),
        ),
        migrations.AlterField(
            model_name="test",
            name="time_limit_min",
            field=models.PositiveIntegerField(
                default=25,
                help_text="Imtihon rejimida beriladigan vaqt.",
                verbose_name="Imtihon vaqti (daqiqa)",
            ),
        ),
    ]
