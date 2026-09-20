from django.contrib import admin
from .models import (
    Employer,
    EmployerRegistrationOTP,
    JobPost,
    JobApplication,
)


# =========================================================
# EMPLOYER
# =========================================================

@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):

    list_display = (
        "company_name",
        "business_permit_no",
        "contact_no",
        "employer",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "company_name",
        "business_permit_no",
        "contact_no",
        "employer__username",
        "employer__email",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "-created_at",
    )


# =========================================================
# EMPLOYER REGISTRATION OTP
# =========================================================

@admin.register(EmployerRegistrationOTP)
class EmployerRegistrationOTPAdmin(admin.ModelAdmin):

    list_display = (
        "username",
        "email",
        "company_name",
        "business_permit_no",
        "contact_no",
        "otp_code",
        "is_verified",
        "created_at",
        "expires_at",
    )

    list_filter = (
        "is_verified",
        "created_at",
        "expires_at",
    )

    search_fields = (
        "username",
        "email",
        "company_name",
        "business_permit_no",
        "contact_no",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "-created_at",
    )


# =========================================================
# JOB POST
# =========================================================

@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "employer",
        "job_type",
        "location",
        "salary_display",
        "vacancies",
        "deadline",
        "status",
        "approved_at",
        "created_at",
    )

    list_filter = (
        "status",
        "job_type",
        "deadline",
        "created_at",
        "approved_at",
    )

    search_fields = (
        "title",
        "description",
        "qualifications",
        "location",
        "employer__company_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "approved_at",
    )

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Job Information",
            {
                "fields": (
                    "employer",
                    "title",
                    "description",
                    "qualifications",
                    "responsibilities",
                )
            },
        ),
        (
            "Employment Details",
            {
                "fields": (
                    "salary",
                    "location",
                    "job_type",
                    "vacancies",
                    "deadline",
                )
            },
        ),
        (
            "Application Review",
            {
                "fields": (
                    "status",
                    "admin_remarks",
                    "approved_at",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


# =========================================================
# JOB APPLICATION
# =========================================================

@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):

    list_display = (
        "applicant",
        "job",
        "get_company",
        "status",
        "applied_at",
    )

    list_filter = (
        "status",
        "applied_at",
    )

    search_fields = (
        "applicant__first_name",
        "applicant__middle_name",
        "applicant__last_name",
        "job__title",
        "job__employer__company_name",
    )

    readonly_fields = (
        "applied_at",
    )

    ordering = (
        "-applied_at",
    )

    fieldsets = (
        (
            "Application",
            {
                "fields": (
                    "job",
                    "applicant",
                    "message",
                )
            },
        ),
        (
            "Documents",
            {
                "fields": (
                    "resume",
                    "cover_letter",
                )
            },
        ),
        (
            "Application Status",
            {
                "fields": (
                    "status",
                    "applied_at",
                )
            },
        ),
    )

    @admin.display(
        description="Company",
        ordering="job__employer__company_name"
    )
    def get_company(self, obj):
        return obj.job.employer.company_name