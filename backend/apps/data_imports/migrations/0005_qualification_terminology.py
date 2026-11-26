from django.db import migrations, models


def forward(apps, schema_editor):
    Batch = apps.get_model('data_imports', 'ImportBatch')
    qs = Batch.objects.using(schema_editor.connection.alias)
    qs.filter(state='previewed').update(state='expired', records=[])
    qs.filter(dataset='programmes').update(dataset='qualifications')


def backward(apps, schema_editor):
    Batch = apps.get_model('data_imports', 'ImportBatch')
    qs = Batch.objects.using(schema_editor.connection.alias)
    qs.filter(state='previewed').update(state='expired', records=[])
    qs.filter(dataset='qualifications').update(dataset='programmes')


class Migration(migrations.Migration):
    dependencies = [('data_imports','0004_curriculum_import'), ('directory','0006_qualification_terminology')]
    operations = [
        migrations.AlterField(model_name='importbatch', name='dataset', field=models.CharField(max_length=14, choices=[('qualifications','Qualifications'),('modules','Modules'),('curriculum','Curriculum'),('topics','Topics'),('faculty','Faculty'),('learners','Learners')])),
        migrations.RunPython(forward, backward),
    ]
