from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("directory", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="facultyprofile",
            name="additional_modules_taught",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
