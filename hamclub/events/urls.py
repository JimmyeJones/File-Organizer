from django.urls import path

from . import views

urlpatterns = [
    path("", views.meeting_list, name="meeting_list"),
    path("<int:pk>/", views.meeting_detail, name="meeting_detail"),
    path("<int:pk>/recording/", views.recording, name="meeting_recording"),
    path("<int:pk>/volunteer/<int:slot_pk>/", views.claim_slot, name="claim_slot"),
]
