from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from user.models import User
from employer.models import Employer, JobPost, JobApplication
from applicant.models import Applicant
from employer.sms import send_sms
from django.contrib import messages

from django.db.models import Count
from django.db.models.functions import TruncWeek, TruncMonth
from django.utils import timezone
from datetime import timedelta

import os
import shutil
from django.core.files import File

def home_view(request):

    # ==========================================
    # FEATURED JOBS
    # Most applicants first
    # ==========================================

    featured_jobs = (
        JobPost.objects
        .filter(status="approved")
        .annotate(
            application_count=Count("applications")
        )
        .order_by(
            "-application_count",
            "-created_at"
        )[:5]
    )

    # ==========================================
    # PORTAL STATISTICS
    # ==========================================

    registered_applicants = Applicant.objects.count()

    active_job_vacancies = JobPost.objects.filter(
        status="approved"
    ).count()

    successful_placements = JobApplication.objects.filter(
        status="accepted"
    ).count()

    # ==========================================
    # RENDER HOME PAGE
    # ==========================================

    return render(
        request,
        "pages/home_view.html",
        {
            "featured_jobs": featured_jobs,
            "registered_applicants": registered_applicants,
            "active_job_vacancies": active_job_vacancies,
            "successful_placements": successful_placements,
        }
    )

def employee_registration(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        company_name = request.POST.get("company_name")
        business_permit_no = request.POST.get("business_permit_no")
        contact_no = request.POST.get("contact_no")
        description = request.POST.get("description")
        company_logo = request.FILES.get("company_logo")

        # Username already exists
        if User.objects.filter(username=username).exists():
            messages.error(
                request,
                "Username already exists.",
                extra_tags="registration"
            )
            return redirect("employee-registration")

        # Email already exists
        if User.objects.filter(email=email).exists():
            messages.error(
                request,
                "Email address is already registered.",
                extra_tags="registration"
            )
            return redirect("employee-registration")

        # Company name already exists
        if Employer.objects.filter(company_name=company_name).exists():
            messages.error(
                request,
                "Company name is already registered.",
                extra_tags="registration"
            )
            return redirect("employee-registration")

        # Business permit already exists
        if Employer.objects.filter(business_permit_no=business_permit_no).exists():
            messages.error(
                request,
                "Business Permit Number already exists.",
                extra_tags="registration"
            )
            return redirect("employee-registration")

        # Contact number already exists
        if Employer.objects.filter(contact_no=contact_no).exists():
            messages.error(
                request,
                "Contact number is already registered.",
                extra_tags="registration"
            )
            return redirect("employee-registration")

        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role="employer"
        )

        # Create Employer Profile
        Employer.objects.create(
            employer=user,
            company_name=company_name,
            business_permit_no=business_permit_no,
            contact_no=contact_no,
            description=description,
            company_logo=company_logo,
        )

        messages.success(
            request,
            "Employer account registered successfully. You may now log in.",
            extra_tags="registration"
        )

        return redirect("login-user")

    return render(request, "pages/register_employer.html")

def applicant_registration(request):

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        password = request.POST.get("password", "")

        # ==========================================
        # CHECK EXISTING USERNAME
        # ==========================================

        if User.objects.filter(username=username).exists():
            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": "Username already exists. Please choose another username."
                }
            )

        # ==========================================
        # CHECK EXISTING EMAIL
        # ==========================================

        if email and User.objects.filter(email=email).exists():
            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": "Email address is already registered. Please use another email."
                }
            )

        # ==========================================
        # CHECK EXISTING PHONE NUMBER
        # ==========================================

        if phone_number and Applicant.objects.filter(
            phone_number=phone_number
        ).exists():
            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": "Phone number is already registered. Please use another phone number."
                }
            )

        # ==========================================
        # CREATE USER
        # ==========================================

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role="applicant",
        )

        # ==========================================
        # CREATE APPLICANT
        # ==========================================

        Applicant.objects.create(
            user=user,
            first_name=request.POST.get("first_name"),
            last_name=request.POST.get("last_name"),
            middle_name=request.POST.get("middle_name"),
            email=email,
            phone_number=phone_number,
            resume=request.FILES.get("resume"),
            cover_letter=request.FILES.get("cover_letter"),
        )

        return redirect("login-user")

    return render(
        request,
        "pages/register_applicant.html"
    )


def login_user(request):
    if request.method == "POST":
        username=request.POST.get('username')
        password=request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if user.role == "employer":
                return redirect('employer-dashboard')
            elif user.role == "applicant":
                return redirect('browse-job')
            else:
                return redirect('login-user')
        return redirect('login-user')
    return render(request, 'pages/login.html')

def logout_user(request):
    logout(request)
    return redirect('login-user')

@login_required(login_url="login_user")
def employer_dashboard(request):
    employer = request.user.employer

    jobs = JobPost.objects.filter(employer=employer)

    applications = JobApplication.objects.filter(
        job__employer=employer
    ).select_related(
        "job",
        "applicant",
        "applicant__user"
    ).order_by("-applied_at")

    # -------------------------
    # Weekly Statistics
    # -------------------------
    today = timezone.now()

    this_week = applications.filter(
        applied_at__gte=today - timedelta(days=7)
    ).count()

    last_week = applications.filter(
        applied_at__gte=today - timedelta(days=14),
        applied_at__lt=today - timedelta(days=7)
    ).count()

    max_week = max(this_week, last_week, 1)

    this_week_percent = int((this_week / max_week) * 100)
    last_week_percent = int((last_week / max_week) * 100)

    # -------------------------
    # Monthly Statistics
    # -------------------------
    monthly = (
        applications
        .annotate(month=TruncMonth("applied_at"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    context = {
        "employer": employer,

        "total_jobs": jobs.count(),
        "total_applications": applications.count(),

        "pending_review": applications.filter(status="pending").count(),
        "reviewing": applications.filter(status="reviewing").count(),
        "shortlisted": applications.filter(status="shortlisted").count(),
        "accepted": applications.filter(status="accepted").count(),
        "rejected": applications.filter(status="rejected").count(),

        "recent_applications": applications[:5],

        # Weekly
        "this_week": this_week,
        "last_week": last_week,
        "this_week_percent": this_week_percent,
        "last_week_percent": last_week_percent,

        # Monthly
        "monthly": monthly,
    }

    return render(
        request,
        "pages/employer-dashboard.html",
        context
    )

# @login_required(login_url="login_user")
def browse_job(request):
    job = JobPost.objects.filter(
        status="approved"
    ).order_by("-created_at")
    return render(request, 'pages/browse_job.html', {"job":job})

@login_required(login_url="login_user")
def job_list(request):
    employer = request.user.employer

    jobs = JobPost.objects.filter(
        employer=employer
    ).order_by("-created_at")

    return render(request, "pages/job_list.html", {
        "jobs": jobs
    })

@login_required(login_url="login_user")
def post_job(request):
    employer = get_object_or_404(
        Employer,
        employer=request.user
    )

    if request.method == "POST":

        salary = request.POST.get("salary")

        # Convert empty salary to None
        if not salary:
            salary = None

        JobPost.objects.create(
            employer=employer,
            title=request.POST.get("title"),
            description=request.POST.get("description"),
            qualifications=request.POST.get("qualifications"),
            responsibilities=request.POST.get("responsibilities"),
            salary=salary,
            location=request.POST.get("location"),
            job_type=request.POST.get("job_type"),
            vacancies=request.POST.get("vacancies"),
            deadline=request.POST.get("deadline"),
        )

        return redirect("job-list")

    return render(
        request,
        "components/job_post_form.html"
    )

@login_required(login_url="login_user")
def update_job(request, id):
    employer = get_object_or_404(Employer, employer=request.user)

    job = get_object_or_404(
        JobPost,
        id=id,
        employer=employer
    )

    if request.method == "POST":
        job.title = request.POST.get("title")
        job.description = request.POST.get("description")
        job.qualifications = request.POST.get("qualifications")
        job.responsibilities = request.POST.get("responsibilities")
        job.salary = request.POST.get("salary")
        job.location = request.POST.get("location")
        job.job_type = request.POST.get("job_type")
        job.vacancies = request.POST.get("vacancies")
        job.deadline = request.POST.get("deadline")

        job.save()

        return redirect("job-list")

    return render(
        request,
        "components/job_post_form.html",
        {
            "job": job
        }
    )

@login_required(login_url="login_user")
def employer_delete_job(request, id):
    employer = get_object_or_404(Employer, employer=request.user)

    # Ensure the job belongs to the logged-in employer
    job = get_object_or_404(
        JobPost,
        id=id,
        employer=employer
    )

    if request.method == "POST":
        job.delete()
        return redirect("job-list")

    return render(request, "components/employer_delete_job.html", {
        "job": job
    })

def job_details(request, id):
    job = get_object_or_404(JobPost, id=id)

    return render(request, "pages/job_details.html", {
        "job": job
    })

def company_profile(request, id):
    company = get_object_or_404(Employer, id=id)

    jobs = JobPost.objects.filter(
        employer=company,
        status="approved"
    )

    return render(request, "pages/company_profile.html", {
        "company": company,
        "jobs": jobs,
    })


@login_required(login_url="login_user")
def apply_job(request, id):

    # =========================================================
    # GET JOB
    # =========================================================

    job = get_object_or_404(
        JobPost,
        id=id
    )

    # =========================================================
    # GET APPLICANT PROFILE
    # =========================================================

    try:

        applicant = request.user.applicant_profile

    except AttributeError:

        messages.error(
            request,
            "Applicant profile not found."
        )

        return redirect(
            "job_details",
            id=job.id
        )

    # =========================================================
    # ONLY APPROVED JOBS CAN RECEIVE APPLICATIONS
    # =========================================================

    if job.status != "approved":

        messages.error(
            request,
            "This job is not currently accepting applications."
        )

        return redirect(
            "job_details",
            id=job.id
        )

    # =========================================================
    # CHECK DUPLICATE APPLICATION
    # =========================================================

    existing_application = JobApplication.objects.filter(
        job=job,
        applicant=applicant
    ).first()

    if existing_application:

        messages.warning(
            request,
            "You have already applied for this job."
        )

        return redirect(
            "my-applications"
        )

    # =========================================================
    # PROCESS APPLICATION
    # =========================================================

    if request.method == "POST":

        message = request.POST.get(
            "message",
            ""
        ).strip()

        uploaded_resume = request.FILES.get(
            "resume"
        )

        uploaded_cover_letter = request.FILES.get(
            "cover_letter"
        )

        # =====================================================
        # FILE VALIDATION FUNCTION
        # =====================================================

        def validate_file(uploaded_file, field_name):

            if not uploaded_file:
                return None

            # Maximum 5 MB
            max_size = 5 * 1024 * 1024

            if uploaded_file.size > max_size:

                return (
                    f"{field_name} must not exceed 5 MB."
                )

            allowed_extensions = [
                ".pdf",
                ".doc",
                ".docx"
            ]

            extension = os.path.splitext(
                uploaded_file.name
            )[1].lower()

            if extension not in allowed_extensions:

                return (
                    f"{field_name} must be a PDF, DOC, or DOCX file."
                )

            return None

        # =====================================================
        # VALIDATE RESUME
        # =====================================================

        resume_error = validate_file(
            uploaded_resume,
            "Resume"
        )

        if resume_error:

            messages.error(
                request,
                resume_error
            )

            return render(
                request,
                "pages/apply_job.html",
                {
                    "job": job,
                    "applicant": applicant,
                    "existing_application": existing_application,
                }
            )

        # =====================================================
        # VALIDATE COVER LETTER
        # =====================================================

        cover_letter_error = validate_file(
            uploaded_cover_letter,
            "Cover letter"
        )

        if cover_letter_error:

            messages.error(
                request,
                cover_letter_error
            )

            return render(
                request,
                "pages/apply_job.html",
                {
                    "job": job,
                    "applicant": applicant,
                    "existing_application": existing_application,
                }
            )

        # =====================================================
        # REQUIRE RESUME
        #
        # Either:
        # - newly uploaded resume
        # - existing applicant resume
        # =====================================================

        if not uploaded_resume and not applicant.resume:

            messages.error(
                request,
                "Please upload a resume before submitting your application."
            )

            return render(
                request,
                "pages/apply_job.html",
                {
                    "job": job,
                    "applicant": applicant,
                    "existing_application": existing_application,
                }
            )

        # =====================================================
        # REQUIRE COVER LETTER
        #
        # Either:
        # - newly uploaded cover letter
        # - existing applicant cover letter
        # =====================================================

        if (
            not uploaded_cover_letter
            and not applicant.cover_letter
        ):

            messages.error(
                request,
                "Please upload a cover letter before submitting your application."
            )

            return render(
                request,
                "pages/apply_job.html",
                {
                    "job": job,
                    "applicant": applicant,
                    "existing_application": existing_application,
                }
            )

        # =====================================================
        # CREATE APPLICATION
        # =====================================================

        application = JobApplication.objects.create(
            job=job,
            applicant=applicant,
            message=message,
            status="pending"
        )

        # =====================================================
        # SAVE RESUME
        #
        # If a new resume was uploaded:
        #     save the uploaded file
        #
        # Otherwise:
        #     copy the applicant's existing file
        # =====================================================

        if uploaded_resume:

            application.resume = uploaded_resume

        elif applicant.resume:

            source_path = applicant.resume.path

            if os.path.exists(source_path):

                with open(
                    source_path,
                    "rb"
                ) as resume_file:

                    application.resume.save(
                        os.path.basename(
                            source_path
                        ),
                        File(resume_file),
                        save=False
                    )

        # =====================================================
        # SAVE COVER LETTER
        #
        # If a new cover letter was uploaded:
        #     save the uploaded file
        #
        # Otherwise:
        #     copy the applicant's existing file
        # =====================================================

        if uploaded_cover_letter:

            application.cover_letter = uploaded_cover_letter

        elif applicant.cover_letter:

            source_path = applicant.cover_letter.path

            if os.path.exists(source_path):

                with open(
                    source_path,
                    "rb"
                ) as cover_letter_file:

                    application.cover_letter.save(
                        os.path.basename(
                            source_path
                        ),
                        File(cover_letter_file),
                        save=False
                    )

        # =====================================================
        # FINAL SAVE
        # =====================================================

        application.save()

        # =====================================================
        # SUCCESS MESSAGE
        # =====================================================

        messages.success(
            request,
            f"Your application for {job.title} has been submitted successfully."
        )

        return redirect(
            "my-applications"
        )

    # =========================================================
    # DISPLAY APPLICATION PAGE
    # =========================================================

    return render(
        request,
        "pages/apply_job.html",
        {
            "job": job,
            "applicant": applicant,
            "existing_application": existing_application,
        }
    )

@login_required(login_url="login_user")
def my_applications(request):
    applications = JobApplication.objects.filter(
        applicant=request.user.applicant_profile
    ).order_by("-applied_at")

    return render(request, "pages/my_applications.html", {
        "applications": applications
    })

@login_required(login_url="login_user")
def applicants(request):
    employer = request.user.employer

    applications = JobApplication.objects.filter(
        job__employer=employer
    ).select_related(
        "applicant",
        "applicant__user",
        "job"
    )

    return render(request, "pages/applicants.html", {
        "applications": applications
    })

@login_required(login_url="login_user")
def update_applicant_status(request, id):
    application = get_object_or_404(JobApplication, id=id)

    # Only the employer who owns the job can update
    if application.job.employer != request.user.employer:
        return redirect("applicants-list")

    if request.method == "POST":
        new_status = request.POST.get("status")

        if new_status in [
            "pending",
            "reviewing",
            "shortlisted",
            "accepted",
            "rejected",
        ]:

            # Only proceed if the status changed
            if application.status != new_status:

                application.status = new_status
                application.save()

                phone = application.applicant.phone_number

                # Convert 0917xxxxxxx -> 63917xxxxxxx
                if phone.startswith("0"):
                    phone = "63" + phone[1:]

                if application.status == "pending":
                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"Your application for the position of "
                        f"{application.job.title} at "
                        f"{application.job.employer.company_name} has been successfully received.\n\n"
                        f"Our recruitment team will review your application, "
                        f"and you will be notified once there are updates.\n\n"
                        f"Thank you for your interest in joining our organization.\n\n"
                        f"{application.job.employer.company_name}"
                    )

                elif application.status == "reviewing":
                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"We would like to inform you that your application "
                        f"for the position of {application.job.title} at "
                        f"{application.job.employer.company_name} is currently under review.\n\n"
                        f"We appreciate your patience and will keep you informed "
                        f"of any further developments.\n\n"
                        f"Thank you.\n"
                        f"{application.job.employer.company_name}"
                    )

                elif application.status == "shortlisted":
                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"Congratulations! You have been shortlisted for the "
                        f"position of {application.job.title} at "
                        f"{application.job.employer.company_name}.\n\n"
                        f"Our Human Resources team will contact you soon "
                        f"regarding the next stage of the recruitment process.\n\n"
                        f"Thank you, and we look forward to speaking with you.\n\n"
                        f"{application.job.employer.company_name}"
                    )

                elif application.status == "accepted":
                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"Congratulations! We are pleased to inform you that "
                        f"you have been selected for the position of "
                        f"{application.job.title} at "
                        f"{application.job.employer.company_name}.\n\n"
                        f"Our Human Resources team will contact you shortly "
                        f"with further instructions regarding your employment.\n\n"
                        f"Welcome to the team, and we wish you every success.\n\n"
                        f"Sincerely,\n"
                        f"{application.job.employer.company_name}"
                    )

                elif application.status == "rejected":
                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"Thank you for your interest in the "
                        f"{application.job.title} position at "
                        f"{application.job.employer.company_name}.\n\n"
                        f"After careful evaluation, we regret to inform you "
                        f"that you have not been selected for this opportunity.\n\n"
                        f"We sincerely appreciate the time and effort you "
                        f"invested in your application and encourage you to "
                        f"apply for future opportunities with us.\n\n"
                        f"We wish you success in your future career.\n\n"
                        f"Sincerely,\n"
                        f"{application.job.employer.company_name}"
                    )

                send_sms(phone, message)

    return redirect("applicants")