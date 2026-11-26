from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('directory', '0005_professional_curriculum')]
    operations = [
        migrations.RenameModel('AcademicProgramme', 'Qualification'),
        migrations.RenameModel('ProgrammeModule', 'QualificationModule'),
        migrations.AddIndex(model_name='qualificationmodule', index=models.Index(fields=['programme'], name='curriculum_qual_idx')),
        migrations.RemoveConstraint(model_name='qualificationmodule', name='uniq_programme_module'),
        migrations.RenameField('qualificationmodule', 'programme', 'qualification'),
        migrations.AlterModelOptions(name='qualificationmodule', options={'ordering': ['qualification_id', 'sequence', 'module_id']}),
        migrations.SeparateDatabaseAndState(state_operations=[
            migrations.RemoveIndex(model_name='qualificationmodule', name='curriculum_qual_idx'),
            migrations.AddIndex(model_name='qualificationmodule', index=models.Index(fields=['qualification'], name='curriculum_qual_idx')),
        ]),
        migrations.AddConstraint(model_name='qualificationmodule', constraint=models.UniqueConstraint(fields=['qualification', 'module'], name='uniq_programme_module')),
        migrations.RenameField('academicmodule', 'programmes', 'qualifications'),
        migrations.RenameField('facultyprofile', 'programmes', 'qualifications'),
        migrations.RenameField('facultyexpertise', 'programmes', 'qualifications'),
        migrations.RenameField('learnerprofile', 'programme', 'qualification'),
    ]
