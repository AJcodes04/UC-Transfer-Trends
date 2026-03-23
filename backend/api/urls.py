from django.urls import path
from . import views

urlpatterns = [
    path('universities/', views.UniversityListView.as_view(), name='university-list'),
    path('majors/', views.MajorListView.as_view(), name='major-list'),
    path('majors/grouped/', views.GroupedMajorListView.as_view(), name='major-list-grouped'),
    path('disciplines/', views.DisciplineListView.as_view(), name='discipline-list'),
    path('transfer-data/', views.TransferDataListView.as_view(), name='transfer-data-list'),
    path('stats/general/', views.GeneralStatsView.as_view(), name='general-stats'),
    path('stats/by-school/<str:school>/', views.SchoolStatsView.as_view(), name='school-stats'),
    path('stats/by-major/<path:major>/', views.MajorStatsView.as_view(), name='major-stats'),
    path('stats/campus-majors/<str:campus>/', views.CampusMajorStatsView.as_view(), name='campus-major-stats'),
]
