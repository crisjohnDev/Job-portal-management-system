from django.db import models
from user.models import User

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

    resume = models.FileField(upload_to="resume/")
    cover_letter = models.FileField(upload_to="cover/")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"