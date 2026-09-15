from django.db import models
from user.models import User
from django.utils import timezone

class Applicant(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="applicant_profile"
    )

    first_name = models.CharField(max_length=266)
    last_name = models.CharField(max_length=266)
    middle_name = models.CharField(max_length=266)

    email = models.EmailField(unique=True)

    phone_number = models.CharField(max_length=11)

    skills = models.TextField(
        blank=True,
        null=True,
        help_text="Enter skills separated by commas. Example: Python, Django, React, SQL"
    )

    resume = models.FileField(upload_to="resume/")
    cover_letter = models.FileField(upload_to="cover/")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class ApplicantRegistrationOTP(models.Model):

    username = models.CharField(max_length=150)

    email = models.EmailField()

    phone_number = models.CharField(max_length=11)

    first_name = models.CharField(max_length=266)
    last_name = models.CharField(max_length=266)
    middle_name = models.CharField(max_length=266)

    password = models.CharField(max_length=255)

    resume = models.FileField(
        upload_to="resume/",
        blank=True,
        null=True
    )

    cover_letter = models.FileField(
        upload_to="cover/",
        blank=True,
        null=True
    )

    skills = models.TextField(
        blank=True,
        null=True
    )

    otp_code = models.CharField(max_length=6)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    expires_at = models.DateTimeField()

    is_verified = models.BooleanField(
        default=False
    )

    def is_expired(self):
        return timezone.now() > self.expires_at