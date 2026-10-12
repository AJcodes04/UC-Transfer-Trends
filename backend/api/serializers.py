"""Response and request shapes. Views pass plain dicts through these so the OpenAPI schema matches reality."""

from rest_framework import serializers

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _gpa_field():
    return serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True, coerce_to_string=False)


class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField(required=False)


class CampusStatsRowSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    campus = serializers.CharField(source='campus_code')
    applicants = serializers.IntegerField()
    admits = serializers.IntegerField()
    enrolls = serializers.IntegerField()
    admit_rate = serializers.IntegerField(allow_null=True)
    yield_rate = serializers.IntegerField(allow_null=True)
    admit_gpa_min = _gpa_field()
    admit_gpa_max = _gpa_field()


class _AggregateRowSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    total_applicants = serializers.IntegerField()
    total_admits = serializers.IntegerField()
    total_enrolls = serializers.IntegerField()
    avg_admit_rate = serializers.FloatField(allow_null=True)
    avg_yield_rate = serializers.FloatField(allow_null=True)
    avg_admit_gpa_min = _gpa_field()
    avg_admit_gpa_max = _gpa_field()


class SchoolStatsRowSerializer(_AggregateRowSerializer):
    college_school = serializers.CharField()


class CampusMajorStatsRowSerializer(_AggregateRowSerializer):
    major_name = serializers.CharField()


class MajorStatsRowSerializer(_AggregateRowSerializer):
    university = serializers.CharField()


class RelatedMajorSerializer(serializers.Serializer):
    name = serializers.CharField()
    campuses = serializers.ListField(child=serializers.CharField())
    latest_year = serializers.IntegerField()


class GroupedMajorSerializer(serializers.Serializer):
    name = serializers.CharField()
    total_applicants = serializers.IntegerField()
    latest_year = serializers.IntegerField()
    campuses = serializers.ListField(child=serializers.CharField())
    related = RelatedMajorSerializer(many=True)


class InstitutionSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class ArticulationMajorSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    academic_year = serializers.CharField()
    row_count = serializers.IntegerField()


class FailedScrapeSerializer(serializers.Serializer):
    major = serializers.CharField()
    academic_year = serializers.CharField(allow_null=True)


class TranscriptCourseSerializer(serializers.Serializer):
    prefix = serializers.CharField()
    number = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    units = serializers.FloatField()
    grade = serializers.CharField(allow_blank=True)
    needs_review = serializers.BooleanField()


class TranscriptParseSerializer(serializers.Serializer):
    college = InstitutionSerializer(allow_null=True)
    courses = TranscriptCourseSerializer(many=True)


class TranscriptUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, uploaded):
        if not uploaded.name.lower().endswith('.pdf'):
            raise serializers.ValidationError('Only PDF files are accepted')
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError('File too large (max 10MB)')
        return uploaded
