from django.db import migrations, models

CODES = {'Diploma in IT':'DIT','BSc Computer Science':'BSCS','MSc Computing':'MSCOMP','BBA':'BBA','MBA':'MBA','BSc Data Science':'BSDS','BA English':'BAENG','Diploma in Business':'DBUS','BSc Information Systems':'BSIS','MSc Data Analytics':'MSDA'}

def populate(apps, schema_editor):
    Programme = apps.get_model('directory','AcademicProgramme')
    reserved = set(CODES.values())
    for p in Programme.objects.all():
        code = CODES.get(p.name, f'LEGACY-{p.pk}')
        if code in reserved and p.name not in CODES:
            code = f'LEGACY-{p.pk}'
        p.code = code
        p.save(update_fields=['code'])
    # Repair only unambiguous existing name references. Keep unresolved legacy names.
    Module = apps.get_model('directory','AcademicModule')
    Faculty = apps.get_model('directory','FacultyProfile')
    for f in Faculty.objects.all():
        remaining = []
        for name in f.additional_modules_taught:
            matches = list(Module.objects.filter(name__iexact=name)[:2])
            if len(matches) == 1:
                f.modules_taught.add(matches[0])
            else:
                remaining.append(name)
        f.additional_modules_taught = remaining
        f.save(update_fields=['additional_modules_taught'])

class Migration(migrations.Migration):
    dependencies = [('directory','0002_faculty_additional_modules_taught')]
    operations = [
        migrations.AddField(model_name='academicprogramme',name='code',field=models.CharField(max_length=30,null=True)),
        migrations.RunPython(populate,migrations.RunPython.noop),
        migrations.AlterField(model_name='academicprogramme',name='code',field=models.CharField(max_length=30,unique=True)),
        migrations.AddField(model_name='academicmodule',name='programmes',field=models.ManyToManyField(blank=True,related_name='modules',to='directory.academicprogramme')),
    ]
