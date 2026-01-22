from django.urls import path

from .views import LoginAPIView, RegisterAPIView, UpdateProfileAPIView, UserMeAPIView

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("update-profile/", UpdateProfileAPIView.as_view(), name="update_profile"),
    path("me/", UserMeAPIView.as_view(), name="users-me"),
]
