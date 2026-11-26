import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="ImportBatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("dataset", models.CharField(choices=[("faculty", "Faculty"), ("learners", "Learners")], max_length=12)),
                ("source_filename", models.CharField(max_length=255)),
                ("state", models.CharField(choices=[("previewed", "Previewed"), ("invalid", "Invalid"), ("confirmed", "Confirmed"), ("failed", "Failed"), ("expired", "Expired")], default="previewed", max_length=12)),
                ("records", models.JSONField(default=list)),
                ("errors", models.JSONField(blank=True, default=list)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("valid_rows", models.PositiveIntegerField(default=0)),
                ("created_count", models.PositiveIntegerField(default=0)),
                ("updated_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
