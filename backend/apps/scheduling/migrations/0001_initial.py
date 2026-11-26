from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    initial=True
    dependencies=[('directory','0006_qualification_terminology'),('nlp','0002_final_result'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='FacultyWindow',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('start',models.DateTimeField()),('end',models.DateTimeField()),('kind',models.CharField(choices=[('available','Available'),('busy','Busy')],max_length=12)),('mode',models.CharField(default='either',max_length=16)),('active',models.BooleanField(default=True)),('faculty',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='directory.facultyprofile')),('created_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL))],options={'ordering':['start','pk']}),
        migrations.CreateModel(name='ScheduleRun',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('created_at',models.DateTimeField(auto_now_add=True)),('result',models.JSONField(default=dict)),('draft',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='schedule_runs',to='nlp.consultationdraft'))],options={'ordering':['-pk']}),
        migrations.CreateModel(name='SlotSelection',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('start',models.DateTimeField()),('end',models.DateTimeField()),('mode',models.CharField(max_length=16)),('updated_at',models.DateTimeField(auto_now=True)),('draft',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='slot_selection',to='nlp.consultationdraft')),('run',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='scheduling.schedulerun')),('faculty',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='directory.facultyprofile'))]),
    ]
