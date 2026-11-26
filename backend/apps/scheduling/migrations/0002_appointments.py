from django.db import migrations, models
import django.db.models.deletion as deletion
from django.conf import settings

class Migration(migrations.Migration):
    dependencies = [('scheduling','0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Appointment', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('start',models.DateTimeField()),('end',models.DateTimeField()),('mode',models.CharField(max_length=16)),
            ('status',models.CharField(max_length=24,default='pending')),('expires_at',models.DateTimeField(null=True,blank=True)),
            ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('draft',models.ForeignKey(on_delete=deletion.PROTECT,related_name='appointments',to='nlp.consultationdraft')),
            ('faculty',models.ForeignKey(on_delete=deletion.PROTECT,to='directory.facultyprofile')),
        ],options={'ordering':['-pk'],'indexes':[models.Index(fields=['faculty','start','end'],name='appt_faculty_time_idx')]}),
        migrations.CreateModel(name='AppointmentEvent',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('action',models.CharField(max_length=32)),('detail',models.JSONField(default=dict)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('actor',models.ForeignKey(null=True,on_delete=deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
            ('appointment',models.ForeignKey(on_delete=deletion.PROTECT,related_name='events',to='scheduling.appointment')),
        ]),
        migrations.CreateModel(name='Notification',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('message',models.CharField(max_length=250)),('created_at',models.DateTimeField(auto_now_add=True)),('read_at',models.DateTimeField(null=True,blank=True)),
            ('recipient',models.ForeignKey(on_delete=deletion.CASCADE,to=settings.AUTH_USER_MODEL)),
            ('appointment',models.ForeignKey(on_delete=deletion.PROTECT,to='scheduling.appointment')),
        ],options={'ordering':['-pk'],'indexes':[models.Index(fields=['recipient','read_at'],name='notification_unread_idx')]}),
    ]
