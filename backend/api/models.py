from django.db import models
from django.db.models import F, Q


def _count_checks(prefix):
    return [
        models.CheckConstraint(condition=Q(applicants__gte=0), name=f'{prefix}_applicants_nonneg'),
        models.CheckConstraint(condition=Q(admits__gte=0), name=f'{prefix}_admits_nonneg'),
        models.CheckConstraint(condition=Q(enrolls__gte=0), name=f'{prefix}_enrolls_nonneg'),
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


def _rate_checks(prefix):
    return [
        models.CheckConstraint(
            condition=Q(admit_rate__isnull=True) | Q(admit_rate__range=(0, 100)),
            name=f'{prefix}_admit_rate_pct',
        ),
        models.CheckConstraint(
            condition=Q(yield_rate__isnull=True) | Q(yield_rate__range=(0, 100)),
            name=f'{prefix}_yield_rate_pct',
        ),
    ]


class Campus(models.Model):
    """A UC campus. `code` is the short form used in UC exports and URLs, e.g. 'UCB'."""
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['code']
        verbose_name_plural = 'Campuses'

    def __str__(self):
        return self.code


class Major(models.Model):
    """
    One row per major spelling found in UC data.

    canonical: set when this spelling is the same major under another name; stats merge into it.
    parent: set when this major is listed under another one for navigation.
    """
    name = models.CharField(max_length=100, unique=True)
    canonical = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='aliases',
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children',
    )

    class Meta:
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=Q(canonical__isnull=True) | Q(parent__isnull=True),
                name='major_alias_has_no_parent',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def canonical_id_or_self(self):
        return self.canonical_id or self.id


class TransferData(models.Model):
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, related_name='transfer_rows')
    year = models.IntegerField(db_index=True)
    broad_discipline = models.CharField(max_length=100)
    college_school = models.CharField(max_length=100)
    major = models.ForeignKey(Major, on_delete=models.PROTECT, related_name='transfer_rows')
    applicants = models.IntegerField()
    admits = models.IntegerField()
    enrolls = models.IntegerField()

    admit_gpa_min = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    admit_gpa_max = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    enroll_gpa_min = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    enroll_gpa_max = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-year', 'campus__code', 'major__name']
        verbose_name = "Transfer Data"
        verbose_name_plural = "Transfer Data"
        constraints = [
            models.UniqueConstraint(
                fields=['campus', 'year', 'major', 'college_school'],
                name='transferdata_unique_campus_year_major_college',
            ),
            *_count_checks('transferdata'),
        ]
        indexes = [
            models.Index(fields=['campus', 'year'], name='transferdata_campus_year_idx'),
        ]

    def __str__(self):
        return f"{self.campus_id} {self.year} - {self.major_id}"


class CampusStats(models.Model):
    """Pre-computed campus-level admission stats from official UC data."""
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, related_name='yearly_stats')
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
        ordering = ['-year', 'campus__code']
        verbose_name = "Campus Stats"
        verbose_name_plural = "Campus Stats"
        constraints = [
            models.UniqueConstraint(fields=['campus', 'year'], name='campusstats_unique_campus_year'),
            *_count_checks('campusstats'),
            *_rate_checks('campusstats'),
        ]

    def __str__(self):
        return f"{self.campus_id} {self.year}"
