from django.db import models
from django.db.models import Q, Avg, Count, Sum
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class AcademicYear(models.Model):
    year = models.CharField(max_length=9, unique=True, help_text="Academic year in format YYYY-YY (e.g., 2023-24)")
    start_year = models.IntegerField(help_text="Starting year (e.g., 2023)")
    end_year = models.IntegerField(help_text="Ending year (e.g., 2024)")
    
    class Meta:
        ordering = ['-start_year']
        verbose_name = "Academic Year"
        verbose_name_plural = "Academic Years"
        indexes = [
            models.Index(fields=['start_year']),
            models.Index(fields=['year']),
        ]
    
    def __str__(self):
        return self.year
    
    def save(self, *args, **kwargs):
        if not self.start_year and self.year:
            parts = self.year.split('-')
            if len(parts) == 2:
                self.start_year = int(parts[0])
                self.end_year = int('20' + parts[1])
        super().save(*args, **kwargs)


class CommunityCollege(models.Model):
    name = models.CharField(max_length=200, unique=True, db_index=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=2, default='CA')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Community College"
        verbose_name_plural = "Community Colleges"
        indexes = [
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_total_transfers(self, uc_campus=None, academic_year=None):
        queryset = self.transfer_data.all()
        if uc_campus:
            queryset = queryset.filter(uc_campus=uc_campus)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        return queryset.aggregate(
            total_applicants=Sum('applicants'),
            total_admits=Sum('admits'),
            total_enrolls=Sum('enrolls')
        )


class UCCampus(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    code = models.CharField(max_length=10, unique=True, db_index=True, help_text="Campus code (e.g., UCB, UCLA)")
    city = models.CharField(max_length=100, blank=True, null=True)
    established_year = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "UC Campus"
        verbose_name_plural = "UC Campuses"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_admission_stats(self, academic_year=None, major=None):
        queryset = self.transfer_data.all()
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if major:
            queryset = queryset.filter(major=major)
        
        stats = queryset.aggregate(
            total_applicants=Sum('applicants'),
            total_admits=Sum('admits'),
            total_enrolls=Sum('enrolls'),
            avg_admit_rate=Avg('acceptance_rate'),
            avg_yield_rate=Avg('yield_rate'),
            avg_gpa=Avg('average_gpa')
        )
        return stats
    
    def get_year_over_year_trend(self, start_year=None, end_year=None):
        queryset = self.transfer_data.select_related('academic_year').all()
        if start_year:
            queryset = queryset.filter(academic_year__start_year__gte=start_year)
        if end_year:
            queryset = queryset.filter(academic_year__start_year__lte=end_year)
        
        return queryset.values('academic_year__year', 'academic_year__start_year').annotate(
            total_applicants=Sum('applicants'),
            total_admits=Sum('admits'),
            total_enrolls=Sum('enrolls'),
            avg_acceptance_rate=Avg('acceptance_rate'),
            avg_gpa=Avg('average_gpa')
        ).order_by('academic_year__start_year')


class Major(models.Model):
    name = models.CharField(max_length=200, db_index=True, help_text="Major name (e.g., Computer Science)")
    broad_discipline = models.CharField(max_length=200, db_index=True, help_text="Broad discipline category (e.g., Engineering)")
    college_school = models.CharField(max_length=200, blank=True, null=True, help_text="College or school within UC campus")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['broad_discipline', 'name']
        verbose_name = "Major"
        verbose_name_plural = "Majors"
        unique_together = [['name', 'broad_discipline']]
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['broad_discipline']),
            models.Index(fields=['name', 'broad_discipline']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.broad_discipline})"
    
    def get_admission_stats(self, uc_campus=None, academic_year=None):
        queryset = self.transfer_data.all()
        if uc_campus:
            queryset = queryset.filter(uc_campus=uc_campus)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        
        return queryset.aggregate(
            total_applicants=Sum('applicants'),
            total_admits=Sum('admits'),
            total_enrolls=Sum('enrolls'),
            avg_acceptance_rate=Avg('acceptance_rate'),
            avg_gpa=Avg('average_gpa'),
            avg_yield_rate=Avg('yield_rate')
        )
    
    def get_campus_comparison(self, academic_year=None):
        queryset = self.transfer_data.select_related('uc_campus').all()
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        
        return queryset.values('uc_campus__name', 'uc_campus__code').annotate(
            total_applicants=Sum('applicants'),
            total_admits=Sum('admits'),
            acceptance_rate=Avg('acceptance_rate'),
            avg_gpa=Avg('average_gpa')
        ).order_by('-acceptance_rate')


class TransferData(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='transfer_data',
        db_index=True
    )
    community_college = models.ForeignKey(
        CommunityCollege,
        on_delete=models.CASCADE,
        related_name='transfer_data',
        db_index=True
    )
    uc_campus = models.ForeignKey(
        UCCampus,
        on_delete=models.CASCADE,
        related_name='transfer_data',
        db_index=True
    )
    major = models.ForeignKey(
        Major,
        on_delete=models.CASCADE,
        related_name='transfer_data',
        db_index=True
    )
    
    applicants = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Number of applicants"
    )
    admits = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Number of admitted students"
    )
    enrolls = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Number of enrolled students"
    )
    
    acceptance_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Acceptance rate as percentage (0-100)"
    )
    
    average_gpa = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(4.0)],
        help_text="Average GPA of admitted students"
    )
    
    gpa_min = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(4.0)],
        help_text="Minimum GPA in range"
    )
    
    gpa_max = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(4.0)],
        help_text="Maximum GPA in range"
    )
    
    yield_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Yield rate as percentage (0-100)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-academic_year__start_year', 'uc_campus', 'major']
        verbose_name = "Transfer Data"
        verbose_name_plural = "Transfer Data"
        unique_together = [
            ['academic_year', 'community_college', 'uc_campus', 'major']
        ]
        indexes = [
            models.Index(fields=['academic_year', 'uc_campus']),
            models.Index(fields=['academic_year', 'major']),
            models.Index(fields=['uc_campus', 'major']),
            models.Index(fields=['community_college', 'uc_campus']),
            models.Index(fields=['acceptance_rate']),
            models.Index(fields=['average_gpa']),
            models.Index(fields=['gpa_min', 'gpa_max']),
            models.Index(fields=['academic_year', 'uc_campus', 'major']),
        ]
    
    def __str__(self):
        return f"{self.academic_year.year} - {self.community_college.name} → {self.uc_campus.name} - {self.major.name}"
    
    def calculate_acceptance_rate(self):
        if self.applicants and self.applicants > 0 and self.admits is not None:
            rate = (Decimal(self.admits) / Decimal(self.applicants)) * 100
            return round(rate, 2)
        return None
    
    def calculate_yield_rate(self):
        if self.admits and self.admits > 0 and self.enrolls is not None:
            rate = (Decimal(self.enrolls) / Decimal(self.admits)) * 100
            return round(rate, 2)
        return None
    
    def calculate_average_gpa(self):
        if self.gpa_min is not None and self.gpa_max is not None:
            return (self.gpa_min + self.gpa_max) / 2
        return None
    
    def save(self, *args, **kwargs):
        if not self.acceptance_rate and self.applicants and self.admits:
            self.acceptance_rate = self.calculate_acceptance_rate()
        
        if not self.yield_rate and self.admits and self.enrolls:
            self.yield_rate = self.calculate_yield_rate()
        
        if not self.average_gpa and self.gpa_min and self.gpa_max:
            self.average_gpa = self.calculate_average_gpa()
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_year_over_year_trend(cls, uc_campus=None, major=None, community_college=None):
        queryset = cls.objects.select_related(
            'academic_year', 'uc_campus', 'major', 'community_college'
        ).all()
        
        if uc_campus:
            queryset = queryset.filter(uc_campus=uc_campus)
        if major:
            queryset = queryset.filter(major=major)
        if community_college:
            queryset = queryset.filter(community_college=community_college)
        
        return queryset.values('academic_year__year', 'academic_year__start_year').annotate(
            total_applicants=Sum('applicants'),
            total_admits=Sum('admits'),
            total_enrolls=Sum('enrolls'),
            avg_acceptance_rate=Avg('acceptance_rate'),
            avg_gpa=Avg('average_gpa'),
            avg_yield_rate=Avg('yield_rate')
        ).order_by('academic_year__start_year')
    
    @classmethod
    def get_campus_comparison(cls, academic_year=None, major=None):
        queryset = cls.objects.select_related('uc_campus', 'academic_year').all()
        
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if major:
            queryset = queryset.filter(major=major)
        
        return queryset.values('uc_campus__name', 'uc_campus__code').annotate(
            total_applicants=Sum('applicants'),
            total_admits=Sum('admits'),
            total_enrolls=Sum('enrolls'),
            avg_acceptance_rate=Avg('acceptance_rate'),
            avg_gpa=Avg('average_gpa'),
            avg_yield_rate=Avg('yield_rate')
        ).order_by('-avg_acceptance_rate')
    
    @classmethod
    def filter_by_gpa_range(cls, min_gpa=None, max_gpa=None):
        queryset = cls.objects.all()
        
        if min_gpa is not None:
            queryset = queryset.filter(
                Q(gpa_min__gte=min_gpa) | Q(gpa_max__gte=min_gpa)
            )
        
        if max_gpa is not None:
            queryset = queryset.filter(
                Q(gpa_min__lte=max_gpa) | Q(gpa_max__lte=max_gpa)
            )
        
        return queryset

