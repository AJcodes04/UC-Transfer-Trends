from django.db import models
from django.db.models import F, Q


def _count_checks(prefix):
    return [
        models.CheckConstraint(condition=Q(applicants__gte=0), name=f'{prefix}_applicants_nonneg'),
        models.CheckConstraint(condition=Q(admits__gte=0), name=f'{prefix}_admits_nonneg'),
        models.CheckConstraint(condition=Q(enrolls__gte=0), name=f'{prefix}_enrolls_nonneg'),
        models.CheckConstraint(
            condition=Q(admit_rate__isnull=True) | Q(admit_rate__range=(0, 100)),
            name=f'{prefix}_admit_rate_pct',
        ),
        models.CheckConstraint(
            condition=Q(yield_rate__isnull=True) | Q(yield_rate__range=(0, 100)),
            name=f'{prefix}_yield_rate_pct',
        ),
        models.CheckConstraint(
            condition=Q(admit_gpa_min__isnull=True) | Q(admit_gpa_max__isnull=True)
            | Q(admit_gpa_min__lte=F('admit_gpa_max')),
            name=f'{prefix}_admit_gpa_ordered',
        ),
        models.CheckConstraint(
            condition=Q(enroll_gpa_min__isnull=True) | Q(enroll_gpa_max__isnull=True)
            | Q(enroll_gpa_min__lte=F('enroll_gpa_max')),
            name=f'{prefix}_enroll_gpa_ordered',
        ),
    ]


class TransferData(models.Model):
    university = models.CharField(max_length=10, db_index=True)
    year = models.IntegerField(db_index=True)
    broad_discipline = models.CharField(max_length=100)
    college_school = models.CharField(max_length=100)
    major_name = models.CharField(max_length=100, db_index=True)
    applicants = models.IntegerField()
    admits = models.IntegerField()
    enrolls = models.IntegerField()

    admit_gpa_min = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    admit_gpa_max = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    enroll_gpa_min = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    enroll_gpa_max = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    admit_rate = models.IntegerField(null=True, blank=True)
    yield_rate = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-year', 'university', 'major_name']
        verbose_name = "Transfer Data"
        verbose_name_plural = "Transfer Data"
        constraints = [
            models.UniqueConstraint(
                fields=['university', 'year', 'major_name', 'college_school'],
                name='transferdata_unique_campus_year_major_college',
            ),
            *_count_checks('transferdata'),
        ]
        indexes = [
            models.Index(fields=['university', 'year']),
        ]

    def __str__(self):
        return f"{self.university} {self.year} - {self.major_name}"


class CampusStats(models.Model):
    """Pre-computed campus-level admission stats from official UC data."""
    campus = models.CharField(max_length=10, db_index=True)
    year = models.IntegerField(db_index=True)

    applicants = models.IntegerField()
    admits = models.IntegerField()
    enrolls = models.IntegerField()

    admit_gpa_min = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    admit_gpa_max = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    enroll_gpa_min = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    enroll_gpa_max = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    admit_rate = models.IntegerField(null=True, blank=True)
    yield_rate = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-year', 'campus']
        verbose_name = "Campus Stats"
        verbose_name_plural = "Campus Stats"
        constraints = [
            models.UniqueConstraint(fields=['campus', 'year'], name='campusstats_unique_campus_year'),
            *_count_checks('campusstats'),
        ]

    def __str__(self):
        return f"{self.campus} {self.year}"
