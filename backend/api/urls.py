from django.urls import path
from . import views
from .transcript import TranscriptUploadView

urlpatterns = [
    # Transcript parsing (stateless PDF upload)
    path('transcript/upload/', TranscriptUploadView.as_view(), name='transcript-upload'),

    path('universities/', views.UniversityListView.as_view(), name='university-list'),
    path('majors/', views.MajorListView.as_view(), name='major-list'),
    path('majors/grouped/', views.GroupedMajorListView.as_view(), name='major-list-grouped'),
    path('disciplines/', views.DisciplineListView.as_view(), name='discipline-list'),
    path('transfer-data/', views.TransferDataListView.as_view(), name='transfer-data-list'),
    path('stats/general/', views.GeneralStatsView.as_view(), name='general-stats'),
    path('stats/by-school/<str:school>/', views.SchoolStatsView.as_view(), name='school-stats'),
    path('stats/by-major/<path:major>/', views.MajorStatsView.as_view(), name='major-stats'),
    path('stats/campus-majors/<str:campus>/', views.CampusMajorStatsView.as_view(), name='campus-major-stats'),

    # Articulation agreement endpoints (serves scraped data from JSON files)
    path('articulation/colleges/', views.ArticulationCollegesView.as_view(), name='articulation-colleges'),
    path('articulation/<str:cc_code>/campuses/', views.ArticulationUCsView.as_view(), name='articulation-campuses'),
    path('articulation/<str:cc_code>/<str:uc_code>/majors/', views.ArticulationMajorsView.as_view(), name='articulation-majors'),
    path('articulation/<str:cc_code>/<str:uc_code>/<str:major_slug>/', views.ArticulationDetailView.as_view(), name='articulation-detail'),
]
