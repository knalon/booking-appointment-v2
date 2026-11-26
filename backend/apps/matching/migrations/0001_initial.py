import uuid
from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL),('nlp','0002_final_result')]
    operations=[
      migrations.CreateModel(name='MatchingPolicy',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('configuration',models.JSONField()),('created_at',models.DateTimeField(auto_now_add=True)),('created_by',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL))]),
      migrations.CreateModel(name='RecommendationRun',fields=[('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('result',models.JSONField(default=dict)),('draft',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='recommendations',to='nlp.consultationdraft')),('policy',models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,to='matching.matchingpolicy'))],options={'ordering':['-created_at','-id']})]
