from django.db import migrations, models

def expire(apps,schema_editor):
    apps.get_model('data_imports','ImportBatch').objects.filter(state='previewed').update(state='expired',records=[])

class Migration(migrations.Migration):
    dependencies=[('data_imports','0001_initial'),('directory','0003_academic_catalogue')]
    operations=[
        migrations.AlterField(model_name='importbatch',name='dataset',field=models.CharField(max_length=12,choices=[('programmes','Programmes'),('modules','Modules'),('faculty','Faculty'),('learners','Learners')])),
        migrations.AddField(model_name='importbatch',name='unchanged_count',field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='importbatch',name='preview_digest',field=models.CharField(max_length=64,blank=True,default='')),
        migrations.RunPython(expire,migrations.RunPython.noop),
    ]
