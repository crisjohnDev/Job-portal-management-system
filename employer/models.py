from django.db import models
from user.models import User
from applicant.models import Applicant

class Employer(models.Model):
    employer = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    business_permit_no = models.CharField(max_length=255, unique=True)
    contact_no = models.CharField(max_length=11, unique=True)
    description = models.TextField()
    company_logo = models.ImageField(upload_to="company_logo")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)



class JobPost(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    JOB_TYPE = (
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("contract", "Contract"),
        ("internship", "Internship"),
        ("temporary", "Temporary"),
    )

    employer = models.ForeignKey(
        Employer,
        on_delete=models.CASCADE,
        related_name="jobs"
    )

    title = models.CharField(max_length=255)
    description = models.TextField()

    qualifications = models.TextField()
    responsibilities = models.TextField(blank=True)

    salary = models.DecimalField(max_digits=10, decimal_places=2)

    location = models.CharField(max_length=255)

    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPE,
        default="full_time"
    )

    vacancies = models.PositiveIntegerField(default=1)

    deadline = models.DateField()

    # Approval Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    admin_remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.status})"


class JobApplication(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("reviewing", "Reviewing"),
        ("shortlisted", "Shortlisted"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    )

    job = models.ForeignKey(
        JobPost,
        on_delete=models.CASCADE,
        related_name="applications"
    )

    applicant = models.ForeignKey(
        Applicant,
        on_delete=models.CASCADE,
        related_name="applications"
    )

    message = models.TextField(blank=True)

    applied_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    class Meta:
        unique_together = ("job", "applicant")

    def __str__(self):
        return f"{self.applicant} - {self.job.title}"