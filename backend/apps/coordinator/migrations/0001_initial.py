from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion as deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [('directory','0006_qualification_terminology'),('nlp','0002_final_result'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='CoordinatorProfile',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('full_name',models.CharField(max_length=160)),
            ('role',models.CharField(max_length=24,choices=[('coordinator','Coordinator'),('programme_manager','Programme Manager')],default='coordinator')),
            ('active',models.BooleanField(default=True)),
            ('qualifications',models.ManyToManyField(related_name='coordinator_profiles',to='directory.qualification')),
            ('user',models.OneToOneField(on_delete=deletion.PROTECT,related_name='coordinator_profile',to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='ReviewCase',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('status',models.CharField(max_length=16,choices=[('open','Open'),('in_review','In review'),('escalated','Escalated'),('resolved','Resolved')],default='open')),
            ('reason',models.CharField(max_length=40)),('trigger_key',models.CharField(max_length=100)),('urgent',models.BooleanField(default=False)),
            ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('assigned_to',models.ForeignKey(blank=True,null=True,on_delete=deletion.PROTECT,to='coordinator.coordinatorprofile')),
            ('draft',models.OneToOneField(on_delete=deletion.PROTECT,related_name='review_case',to='nlp.consultationdraft')),
            ('qualification',models.ForeignKey(null=True,on_delete=deletion.PROTECT,to='directory.qualification')),
        ],options={'ordering':['-urgent','-updated_at','-pk']}),
        migrations.CreateModel(name='ReviewEvent',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('action',models.CharField(max_length=32)),('detail',models.CharField(blank=True,max_length=1000)),('learner_visible',models.BooleanField(default=False)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('actor',models.ForeignKey(null=True,on_delete=deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
            ('case',models.ForeignKey(on_delete=deletion.PROTECT,related_name='events',to='coordinator.reviewcase')),
        ],options={'ordering':['pk']}),
    ]
