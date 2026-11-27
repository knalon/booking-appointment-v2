from django.db import migrations, models
import django.db.models.deletion as deletion

class Migration(migrations.Migration):
    dependencies = [('scheduling','0002_appointments'),('coordinator','0001_initial')]
    operations = [
        migrations.AlterField(model_name='notification',name='appointment',field=models.ForeignKey(blank=True,null=True,on_delete=deletion.PROTECT,to='scheduling.appointment')),
        migrations.AddField(model_name='notification',name='review_case',field=models.ForeignKey(blank=True,null=True,on_delete=deletion.PROTECT,to='coordinator.reviewcase')),
        migrations.AddConstraint(model_name='notification',constraint=models.CheckConstraint(condition=(models.Q(appointment__isnull=False,review_case__isnull=True)|models.Q(appointment__isnull=True,review_case__isnull=False)),name='notification_one_target')),
    ]
