from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='peso-login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.peso_dashboard, name='peso-dashboard'),
    path('employer-list/', views.employer_list, name='employer-list'),
    path('approve-job-post/<int:id>/', views.approve_job, name="approved-job"),
    path('delete-job/<int:id>/', views.delete_job, name="delete-job"),
    path('job-list/', views.job_list, name="job-post-list"),
    path("employers/<int:id>/", views.employer_detail, name="employer_detail"),
    path("employers/<int:id>/suspend/", views.suspend_employer, name="suspend_employer"),
    path("employers/<int:id>/delete/", views.delete_employer, name="delete_employer"),
    path("jobs/<int:id>/", views.view_job, name="view-job",),
    path("applicants/", views.applicant_list, name="applicant-list"),
    path("reports/", views.reports, name="reports"),
    path("admin/applicants/delete-selected/", views.delete_selected_applicants, name="delete-selected-applicants"),
]
