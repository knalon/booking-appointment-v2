import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion as deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('directory','0006_qualification_terminology')]
    operations = [
        migrations.CreateModel(name='ConversationSession', fields=[('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('status',models.CharField(default='active',max_length=20)),('turns',models.PositiveIntegerField(default=0)),('input_tokens',models.PositiveIntegerField(default=0)),('output_tokens',models.PositiveIntegerField(default=0)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('owner',models.ForeignKey(on_delete=deletion.CASCADE,to=settings.AUTH_USER_MODEL)),('learner',models.ForeignKey(on_delete=deletion.PROTECT,to='directory.learnerprofile'))]),
        migrations.CreateModel(name='ConversationMessage',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('role',models.CharField(max_length=12)),('content',models.TextField()),('created_at',models.DateTimeField(auto_now_add=True)),('session',models.ForeignKey(on_delete=deletion.CASCADE,related_name='messages',to='nlp.conversationsession'))],options={'ordering':['pk']}),
        migrations.CreateModel(name='ConsultationDraft',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('data',models.JSONField(default=dict)),('confirmed_at',models.DateTimeField(blank=True,null=True)),('session',models.OneToOneField(on_delete=deletion.CASCADE,related_name='draft',to='nlp.conversationsession'))]),
    ]
