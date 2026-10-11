from django.urls import path

from .views import articulation, health, majors, stats
from .views.transcript import TranscriptUploadView

urlpatterns = [
    path('health/', health.HealthView.as_view(), name='health'),
    path('transcript/upload/', TranscriptUploadView.as_view(), name='transcript-upload'),

    path('universities/', majors.UniversityListView.as_view(), name='university-list'),
    path('majors/', majors.MajorListView.as_view(), name='major-list'),
    path('majors/grouped/', majors.GroupedMajorListView.as_view(), name='major-list-grouped'),
    path('disciplines/', majors.DisciplineListView.as_view(), name='discipline-list'),
    path('transfer-data/', majors.TransferDataListView.as_view(), name='transfer-data-list'),
    path('stats/general/', stats.GeneralStatsView.as_view(), name='general-stats'),
    path('stats/by-school/<str:school>/', stats.SchoolStatsView.as_view(), name='school-stats'),
    path('stats/by-major/<path:major>/', stats.MajorStatsView.as_view(), name='major-stats'),
    path('stats/campus-majors/<str:campus>/', stats.CampusMajorStatsView.as_view(), name='campus-major-stats'),

    path('articulation/colleges/', articulation.ArticulationCollegesView.as_view(), name='articulation-colleges'),
    path('articulation/<str:cc_code>/campuses/', articulation.ArticulationUCsView.as_view(), name='articulation-campuses'),
    path('articulation/<str:cc_code>/<str:uc_code>/majors/', articulation.ArticulationMajorsView.as_view(), name='articulation-majors'),
    # 'failed/' must precede the '<major_slug>' catch-all or "failed" would be read as a slug.
    path('articulation/<str:cc_code>/<str:uc_code>/failed/', articulation.ArticulationFailedView.as_view(), name='articulation-failed'),
    path('articulation/<str:cc_code>/<str:uc_code>/<str:major_slug>/', articulation.ArticulationDetailView.as_view(), name='articulation-detail'),
]
