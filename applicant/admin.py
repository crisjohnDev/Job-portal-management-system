from django.contrib import admin
from .models import Applicant, ApplicantRegistrationOTP


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "first_name",
        "middle_name",
        "last_name",
        "email",
        "phone_number",
        "user",
    )

    search_fields = (
        "first_name",
        "middle_name",
        "last_name",
        "email",
        "phone_number",
        "user__username",
    )

    list_filter = (
        "user",
    )

    ordering = (
        "-id",
    )


@admin.register(ApplicantRegistrationOTP)
class ApplicantRegistrationOTPAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "username",
        "email",
        "phone_number",
        "otp_code",
        "is_verified",
        "created_at",
        "expires_at",
    )

    search_fields = (
        "username",
        "email",
        "phone_number",
        "otp_code",
    )

    list_filter = (
        "is_verified",
        "created_at",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "created_at",
    )