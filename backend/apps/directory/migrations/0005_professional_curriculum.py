from django.db import migrations, models
import django.db.models.deletion as deletion


def copy_old(apps, schema_editor):
    Module = apps.get_model('directory','AcademicModule')
    Programme = apps.get_model('directory','AcademicProgramme')
    Curriculum = apps.get_model('directory','ProgrammeModule')
    Learner = apps.get_model('directory','LearnerProfile')
    db = schema_editor.connection.alias
    for p in Programme.objects.using(db).all():
        for n,m in enumerate(p.modules.order_by('code'),1):
            Curriculum.objects.using(db).create(programme_id=p.pk,module_id=m.pk,sequence=n)
    for learner in Learner.objects.using(db).exclude(current_module=None):
        learner.current_modules.add(learner.current_module_id)


class Migration(migrations.Migration):
    dependencies=[('directory','0004_academic_topics')]
    operations=[
        migrations.CreateModel(name='ProgrammeModule',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('sequence',models.PositiveIntegerField(default=1)),('is_active',models.BooleanField(default=True)),('programme',models.ForeignKey(on_delete=deletion.PROTECT,related_name='curriculum',to='directory.academicprogramme')),('module',models.ForeignKey(on_delete=deletion.PROTECT,related_name='curriculum',to='directory.academicmodule'))],options={'ordering':['programme_id','sequence','module_id'],'constraints':[models.UniqueConstraint(fields=['programme','module'],name='uniq_programme_module')]}),
        migrations.AddField(model_name='learnerprofile',name='current_modules',field=models.ManyToManyField(blank=True,related_name='current_learners',to='directory.academicmodule')),
        migrations.RunPython(copy_old),
        migrations.RemoveField(model_name='academicmodule',name='programmes'),
        migrations.AddField(model_name='academicmodule',name='programmes',field=models.ManyToManyField(blank=True,related_name='modules',through='directory.ProgrammeModule',to='directory.academicprogramme')),
    ]
