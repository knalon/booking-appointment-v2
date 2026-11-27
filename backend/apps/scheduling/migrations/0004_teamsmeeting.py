from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('scheduling','0003_review_notifications')]
    operations=[migrations.CreateModel(name='TeamsMeeting',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('status',models.CharField(default='queued',max_length=24)),('event_id',models.TextField(blank=True)),('join_url',models.TextField(blank=True)),
        ('requested_start',models.DateTimeField(null=True)),('requested_end',models.DateTimeField(null=True)),('detail',models.CharField(blank=True,max_length=250)),('test_mode',models.BooleanField(default=True)),('updated_at',models.DateTimeField(auto_now=True)),
        ('appointment',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='teams_meeting',to='scheduling.appointment'))])]
