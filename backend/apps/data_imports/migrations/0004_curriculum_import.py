from django.db import migrations, models

def expire(apps,schema_editor):
    apps.get_model('data_imports','ImportBatch').objects.filter(state='previewed').update(state='expired',records=[])

class Migration(migrations.Migration):
    dependencies=[('data_imports','0003_topic_import'),('directory','0005_professional_curriculum')]
    operations=[migrations.AlterField(model_name='importbatch',name='dataset',field=models.CharField(max_length=12,choices=[('programmes','Programmes'),('modules','Modules'),('curriculum','Curriculum'),('topics','Topics'),('faculty','Faculty'),('learners','Learners')])),migrations.RunPython(expire,migrations.RunPython.noop)]
