from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class TransferData(models.Model):
    university = models.CharField(max_length=10, db_index=True)
    year = models.IntegerField(db_index=True)
    broad_discipline = models.CharField(max_length=100)
    college_school = models.CharField(max_length=100)
    major_name = models.CharField(max_length=100, db_index=True)

    applicants = models.IntegerField(validators=[MinValueValidator(0)])
    admits = models.IntegerField(validators=[MinValueValidator(0)])
    enrolls = models.IntegerField(validators=[MinValueValidator(0)])

    admit_gpa_min = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    admit_gpa_max = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    enroll_gpa_min = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    enroll_gpa_max = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )

    admit_rate = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    yield_rate = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        ordering = ['-year', 'university', 'major_name']
        verbose_name = "Transfer Data"
        verbose_name_plural = "Transfer Data"
        unique_together = [['university', 'year', 'major_name', 'college_school']]
        indexes = [
            models.Index(fields=['university', 'year']),
            models.Index(fields=['year', 'major_name']),
            models.Index(fields=['broad_discipline']),
            models.Index(fields=['university', 'year', 'major_name']),
        ]

    def __str__(self):
        return f"{self.university} {self.year} - {self.major_name}"
