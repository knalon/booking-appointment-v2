from django.db import migrations, models

def expire(apps,schema_editor):
    apps.get_model('data_imports','ImportBatch').objects.filter(state='previewed').update(state='expired',records=[])

class Migration(migrations.Migration):
    dependencies=[('data_imports','0002_catalogue_import'),('directory','0004_academic_topics')]
    operations=[migrations.AlterField(model_name='importbatch',name='dataset',field=models.CharField(max_length=12,choices=[('programmes','Programmes'),('modules','Modules'),('topics','Topics'),('faculty','Faculty'),('learners','Learners')])),migrations.RunPython(expire,migrations.RunPython.noop)]
