from django.conf import settings
from django.db import models


class Qualification(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=160, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class AcademicModule(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=160)
    department = models.CharField(max_length=120, blank=True)
    qualifications = models.ManyToManyField(Qualification, blank=True, related_name="modules", through="QualificationModule")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class QualificationModule(models.Model):
    qualification = models.ForeignKey(Qualification, on_delete=models.PROTECT, related_name="curriculum")
    module = models.ForeignKey(AcademicModule, on_delete=models.PROTECT, related_name="curriculum")
    sequence = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['qualification_id', 'sequence', 'module_id']
        indexes = [models.Index(fields=['qualification'], name='curriculum_qual_idx')]
        constraints = [models.UniqueConstraint(fields=['qualification','module'], name='uniq_programme_module')]

    def __str__(self):
        return f"{self.qualification.code} / {self.sequence} / {self.module.code}"


class AcademicTopic(models.Model):
    code = models.CharField(max_length=30, unique=True)
    module = models.ForeignKey(AcademicModule, on_delete=models.PROTECT, related_name="topic_catalogue")
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["module", "name"], name="uniq_module_topic_name")]

    def __str__(self):
        return f"{self.module.code} — {self.name}"


class FacultyProfile(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="faculty_profile",
    )
    faculty_id = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    department = models.CharField(max_length=120, blank=True)
    qualifications = models.ManyToManyField(Qualification, blank=True, related_name="faculty")
    modules_taught = models.ManyToManyField(AcademicModule, blank=True, related_name="faculty")
    # Keeps module names from the source CSV when the source does not provide a
    # canonical module code. These can be reconciled against the catalogue later.
    additional_modules_taught = models.JSONField(default=list, blank=True)
    teaching_experience_years = models.PositiveSmallIntegerField(default=0)
    consultation_modes = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    time_zone = models.CharField(max_length=80, default="Asia/Yangon")
    working_days = models.JSONField(default=list, blank=True)
    working_hours_start = models.TimeField(null=True, blank=True)
    working_hours_end = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.faculty_id} - {self.full_name}"


class FacultyExpertise(models.Model):
    class Level(models.TextChoices):
        BASIC = "Basic", "Basic"
        INTERMEDIATE = "Intermediate", "Intermediate"
        ADVANCED = "Advanced", "Advanced"
        EXPERT = "Expert", "Expert"

    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE, related_name="expertise_mappings")
    module = models.ForeignKey(AcademicModule, on_delete=models.PROTECT, related_name="faculty_expertise")
    topics = models.JSONField(default=list, blank=True)  # Legacy migration snapshot; not used for matching.
    catalogue_topics = models.ManyToManyField(AcademicTopic, blank=True, related_name="faculty_expertise")
    expertise_level = models.CharField(max_length=20, choices=Level.choices)
    qualifications = models.ManyToManyField(Qualification, blank=True, related_name="faculty_expertise")
    verified_by = models.CharField(max_length=160, blank=True)
    last_reviewed = models.DateField(null=True, blank=True)
    eligible_for_consultation = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["faculty", "module"], name="uniq_faculty_module_expertise")
        ]


class LearnerProfile(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="learner_profile",
    )
    learner_id = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    qualification = models.ForeignKey(Qualification, null=True, blank=True, on_delete=models.PROTECT)
    current_module = models.ForeignKey(AcademicModule, null=True, blank=True, on_delete=models.PROTECT)
    current_modules = models.ManyToManyField(AcademicModule, blank=True, related_name="current_learners")
    time_zone = models.CharField(max_length=80, default="Asia/Yangon")
    preferred_consultation_modes = models.JSONField(default=list, blank=True)
    preferred_languages = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.learner_id} - {self.full_name}"
