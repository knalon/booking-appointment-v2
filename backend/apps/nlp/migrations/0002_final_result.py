from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('nlp','0001_initial')]
    operations=[migrations.AddField(model_name='consultationdraft',name='final_result',field=models.JSONField(null=True,blank=True))]
