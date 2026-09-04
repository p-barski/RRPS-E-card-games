from django.urls import path

from apps.games import views

urlpatterns = [
    path("rooms/", views.create_room, name="create_room"),
    path("rooms/<str:code>/", views.get_room, name="get_room"),
    path("rooms/<str:code>/join/", views.join_room, name="join_room"),
]
