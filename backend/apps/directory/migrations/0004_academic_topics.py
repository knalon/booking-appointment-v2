import hashlib
from django.db import migrations, models
import django.db.models.deletion


def reconcile(apps, schema_editor):
    Topic = apps.get_model('directory', 'AcademicTopic')
    Expertise = apps.get_model('directory', 'FacultyExpertise')
    db = schema_editor.connection.alias
    for exp in Expertise.objects.using(db).select_related('module'):
        for raw in exp.topics or []:
            if not isinstance(raw, str) or not raw.strip():
                continue
            name = ' '.join(raw.split())
            key = name.casefold()
            code = exp.module.code[:16] + '-T' + hashlib.sha256((exp.module.code+'\0'+key).encode()).hexdigest()[:12].upper()
            topic, _ = Topic.objects.using(db).get_or_create(code=code, defaults={'module_id':exp.module_id,'name':name[:160]})
            exp.catalogue_topics.add(topic)


class Migration(migrations.Migration):
    dependencies=[('directory','0003_academic_catalogue')]
    operations=[
        migrations.CreateModel(name='AcademicTopic',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('code',models.CharField(max_length=30,unique=True)),('name',models.CharField(max_length=160)),('is_active',models.BooleanField(default=True)),('module',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='topic_catalogue',to='directory.academicmodule'))],options={'constraints':[models.UniqueConstraint(fields=('module','name'),name='uniq_module_topic_name')]}),
        migrations.AddField(model_name='facultyexpertise',name='catalogue_topics',field=models.ManyToManyField(blank=True,related_name='faculty_expertise',to='directory.academictopic')),
        migrations.RunPython(reconcile,migrations.RunPython.noop),
    ]
