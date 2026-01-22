from django.urls import path

from .views import (
    AcceptInviteAPIView,
    MyAppointedProjectsAPIView,
    OrganizationCreateAPIView,
    OrganizationInvitationsListAPIView,
    OrganizationInviteCreateAPIView,
    OrganizationMeAPIView,
    OrganizationMemberRoleUpdateAPIView,
    OrganizationMembersListAPIView,
    OrganizationMeUpdateAPIView,
    OrganizationUsersAPIView,
    ProjectCreateAPIView,
    ProjectDetailAPIView,
    ProjectListAPIView,
    ProjectUpdateAPIView,
)

urlpatterns = [
    path("orgs/", OrganizationCreateAPIView.as_view(), name="org-create"),
    path("orgs/me/", OrganizationMeAPIView.as_view(), name="org-me"),
    path(
        "orgs/me/update/", OrganizationMeUpdateAPIView.as_view(), name="org-me-update"
    ),
    path(
        "orgs/invitations-create/",
        OrganizationInviteCreateAPIView.as_view(),
        name="org-invite",
    ),
    path(
        "orgs/accept/invite/", AcceptInviteAPIView.as_view(), name="org-accept-invite"
    ),
    path(
        "orgs/members/",
        OrganizationMembersListAPIView.as_view(),
        name="org-members-list",
    ),
    path(
        "orgs/members/<int:id>/role/",
        OrganizationMemberRoleUpdateAPIView.as_view(),
        name="org-member-role-update",
    ),
    path(
        "orgs/invitations/",
        OrganizationInvitationsListAPIView.as_view(),
        name="org-invitations-list",
    ),
    path("orgs/project-create/", ProjectCreateAPIView.as_view(), name="project-create"),
    path("orgs/users/", OrganizationUsersAPIView.as_view(), name="org-users-list"),
    path("orgs/project-list/", ProjectListAPIView.as_view(), name="org-project-list"),
    path(
        "orgs/my-project-list/",
        MyAppointedProjectsAPIView.as_view(),
        name="org-my-project-list",
    ),
    path(
        "orgs/project-update/<int:id>/",
        ProjectUpdateAPIView.as_view(),
        name="org-project-update",
    ),
    path(
        "orgs/project-detail/<int:id>/",
        ProjectDetailAPIView.as_view(),
        name="org-project-detail",
    ),
]
