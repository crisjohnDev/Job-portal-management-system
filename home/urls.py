from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('employee-registration/', views.employee_registration, name='employee-registration'),
    path('applicant-registration/', views.applicant_registration, name='applicant-registration'),
    path('login/', views.login_user, name='login-user'),
    path('employer-dashboard/', views.employer_dashboard, name='employer-dashboard'),
    path('browse-job/', views.browse_job, name="browse-job"),
    path('job-list/', views.job_list, name="job-list"),
    path('post-job/', views.post_job, name="job-post"),
    path('post-job-update/<int:id>/', views.update_job, name="update-job"),
    path("job/delete/<int:id>/", views.employer_delete_job, name="employer-delete-job"),
    path("jobs/<int:id>/", views.job_details, name="job_details"),
    path("company/<int:id>/", views.company_profile, name="company_profile"),
    path('logut/', views.logout_user, name='logout_user'),
    path("job/<int:id>/apply/", views.apply_job, name="apply-job"),
    path("my-applications/", views.my_applications, name="my-applications"),
    path('applicants-list/', views.applicants, name='applicants'),
    path("application/<int:id>/status/", views.update_applicant_status, name="update-applicant-status"),

]
