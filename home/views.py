from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from user.models import User
from employer.models import Employer, JobPost, JobApplication, EmployerRegistrationOTP
from applicant.models import Applicant, ApplicantRegistrationOTP
from employer.sms import send_sms
from django.contrib import messages
import re
from django.db.models import Count
from django.db.models.functions import TruncWeek, TruncMonth
from django.utils import timezone
from datetime import timedelta
import csv
import io
import os
import shutil
from django.core.files import File
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.db import transaction
import random
from django.contrib.auth.hashers import make_password

from .utils import (
    format_ph_mobile,
    send_iprog_sms
)

def normalize_skill(skill):
    """
    Normalize a skill for matching.
    """
    return re.sub(r"\s+", " ", skill.strip().lower())


def skill_matches_text(skill, text):
    """
    Check whether a skill appears in the job information.

    Uses whole-word matching for simple skills such as:
    Python, Java, SQL, Django

    Uses normal substring matching for skills containing
    special characters such as:
    C++, C#, Node.js, .NET
    """

    skill = normalize_skill(skill)
    text = normalize_skill(text)

    if not skill:
        return False

    # Skills containing special characters
    if re.search(r"[^\w\s]", skill):
        return skill in text

    # Whole-word matching
    return re.search(
        rf"\b{re.escape(skill)}\b",
        text
    ) is not None


def get_job_recommendation(job, applicant_skills):
    """
    Calculate how closely a job matches the applicant's skills.
    """

    if not applicant_skills:
        return 0, []

    # Combine all relevant job information
    job_text = " ".join([
        str(getattr(job, "title", "") or ""),
        str(getattr(job, "description", "") or ""),
        str(getattr(job, "qualifications", "") or ""),
        str(getattr(job, "responsibilities", "") or ""),
        str(getattr(job, "location", "") or ""),
    ])

    # Applicant skills can be separated by:
    # comma
    # semicolon
    # new line
    # |
    raw_skills = re.split(
        r"[,;\n|]+",
        applicant_skills
    )

    normalized_skills = []

    for raw_skill in raw_skills:

        skill = normalize_skill(raw_skill)

        if skill and skill not in normalized_skills:
            normalized_skills.append(skill)

    if not normalized_skills:
        return 0, []

    matched_skills = []

    for skill in normalized_skills:

        if skill_matches_text(
            skill,
            job_text
        ):
            matched_skills.append(skill)

    # Calculate percentage
    score = round(
        (
            len(matched_skills)
            / len(normalized_skills)
        ) * 100
    )

    return score, matched_skills


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

        username = request.POST.get(
            "username",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        company_name = request.POST.get(
            "company_name",
            ""
        ).strip()

        business_permit_no = request.POST.get(
            "business_permit_no",
            ""
        ).strip()

        contact_no = request.POST.get(
            "contact_no",
            ""
        ).strip()

        description = request.POST.get(
            "description",
            ""
        ).strip()

        company_logo = request.FILES.get(
            "company_logo"
        )

        # ==========================================
        # CHECK USERNAME
        # ==========================================

        if User.objects.filter(
            username=username
        ).exists():

            messages.error(
                request,
                "Username already exists.",
                extra_tags="registration"
            )

            return redirect(
                "employee-registration"
            )

        # ==========================================
        # CHECK EMAIL
        # ==========================================

        if User.objects.filter(
            email=email
        ).exists():

            messages.error(
                request,
                "Email address is already registered.",
                extra_tags="registration"
            )

            return redirect(
                "employee-registration"
            )

        # ==========================================
        # CHECK COMPANY
        # ==========================================

        if Employer.objects.filter(
            company_name=company_name
        ).exists():

            messages.error(
                request,
                "Company name is already registered.",
                extra_tags="registration"
            )

            return redirect(
                "employee-registration"
            )

        # ==========================================
        # CHECK BUSINESS PERMIT
        # ==========================================

        if Employer.objects.filter(
            business_permit_no=business_permit_no
        ).exists():

            messages.error(
                request,
                "Business Permit Number already exists.",
                extra_tags="registration"
            )

            return redirect(
                "employee-registration"
            )

        # ==========================================
        # CHECK CONTACT NUMBER
        # ==========================================

        if Employer.objects.filter(
            contact_no=contact_no
        ).exists():

            messages.error(
                request,
                "Contact number is already registered.",
                extra_tags="registration"
            )

            return redirect(
                "employee-registration"
            )

        # ==========================================
        # FORMAT MOBILE NUMBER
        # ==========================================

        phone_number = format_ph_mobile(
            contact_no
        )

        # ==========================================
        # GENERATE OTP
        # ==========================================

        otp_code = str(
            random.randint(
                100000,
                999999
            )
        )

        # ==========================================
        # DELETE OLD PENDING REGISTRATION
        # ==========================================

        EmployerRegistrationOTP.objects.filter(
            email=email,
            is_verified=False
        ).delete()

        # ==========================================
        # CREATE TEMPORARY REGISTRATION
        # ==========================================

        registration = EmployerRegistrationOTP.objects.create(

            username=username,

            email=email,

            password=password,

            company_name=company_name,

            business_permit_no=business_permit_no,

            contact_no=contact_no,

            description=description,

            company_logo=company_logo,

            otp_code=otp_code,

            expires_at=timezone.now()
            + timedelta(minutes=5)
        )

        # ==========================================
        # SMS MESSAGE
        # ==========================================

        sms_message = (
            f"Your employer registration "
            f"verification code is {otp_code}. "
            f"This code will expire in 5 minutes."
        )

        # ==========================================
        # SEND SMS
        # ==========================================

        try:

            response = send_iprog_sms(
                phone_number,
                sms_message
            )

            if response.status_code not in [
                200,
                201
            ]:

                registration.delete()

                messages.error(
                    request,
                    "Unable to send verification code. Please try again.",
                    extra_tags="registration"
                )

                return redirect(
                    "employee-registration"
                )

        except Exception as e:

            registration.delete()

            messages.error(
                request,
                "SMS service is currently unavailable. Please try again.",
                extra_tags="registration"
            )

            return redirect(
                "employee-registration"
            )

        # ==========================================
        # SAVE REGISTRATION ID IN SESSION
        # ==========================================

        request.session[
            "employer_registration_id"
        ] = registration.id

        # ==========================================
        # GO TO OTP PAGE
        # ==========================================

        return redirect(
            "verify-employer-registration"
        )

    return render(
        request,
        "pages/register_employer.html"
    )


def verify_employer_registration(request):

    registration_id = request.session.get(
        "employer_registration_id"
    )

    # ==========================================
    # CHECK SESSION
    # ==========================================

    if not registration_id:

        messages.error(
            request,
            "Registration session expired. Please register again.",
            extra_tags="registration"
        )

        return redirect(
            "employee-registration"
        )

    # ==========================================
    # GET REGISTRATION
    # ==========================================

    try:

        registration = EmployerRegistrationOTP.objects.get(
            id=registration_id,
            is_verified=False
        )

    except EmployerRegistrationOTP.DoesNotExist:

        messages.error(
            request,
            "Registration request was not found.",
            extra_tags="registration"
        )

        return redirect(
            "employee-registration"
        )

    # ==========================================
    # CHECK OTP EXPIRATION
    # ==========================================

    if registration.is_expired():

        registration.delete()

        request.session.pop(
            "employer_registration_id",
            None
        )

        messages.error(
            request,
            "Verification code has expired. Please register again.",
            extra_tags="registration"
        )

        return redirect(
            "employee-registration"
        )

    # ==========================================
    # VERIFY OTP
    # ==========================================

    if request.method == "POST":

        otp = request.POST.get(
            "otp",
            ""
        ).strip()

        # ======================================
        # INVALID OTP
        # ======================================

        if otp != registration.otp_code:

            messages.error(
                request,
                "Invalid verification code.",
                extra_tags="registration"
            )

            return render(
                request,
                "pages/verify_employer.html"
            )

        # ======================================
        # MARK VERIFIED
        # ======================================

        registration.is_verified = True

        registration.save()

        # ======================================
        # CREATE USER
        # ======================================

        user = User.objects.create_user(
            username=registration.username,
            email=registration.email,
            password=registration.password,
            role="employer"
        )

        # ======================================
        # CREATE EMPLOYER PROFILE
        # ======================================

        Employer.objects.create(
            employer=user,

            company_name=registration.company_name,

            business_permit_no=registration.business_permit_no,

            contact_no=registration.contact_no,

            description=registration.description,

            company_logo=registration.company_logo,
        )

        # ======================================
        # DELETE TEMPORARY REGISTRATION
        # ======================================

        registration.delete()

        # ======================================
        # CLEAR SESSION
        # ======================================

        request.session.pop(
            "employer_registration_id",
            None
        )

        # ======================================
        # SUCCESS
        # ======================================

        messages.success(
            request,
            "Employer account registered successfully. You may now log in.",
            extra_tags="registration"
        )

        return redirect(
            "login-user"
        )

    return render(
        request,
        "pages/verify_employer.html"
    )

def applicant_registration(request):

    if request.method == "POST":

        # ==========================================
        # GET FORM DATA
        # ==========================================

        username = request.POST.get(
            "username",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        phone_number = request.POST.get(
            "phone_number",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        first_name = request.POST.get(
            "first_name",
            ""
        ).strip()

        last_name = request.POST.get(
            "last_name",
            ""
        ).strip()

        middle_name = request.POST.get(
            "middle_name",
            ""
        ).strip()

        skills = request.POST.get(
            "skills",
            ""
        ).strip()

        resume = request.FILES.get(
            "resume"
        )

        cover_letter = request.FILES.get(
            "cover_letter"
        )

        # ==========================================
        # CHECK USERNAME
        # ==========================================

        if User.objects.filter(
            username=username
        ).exists():

            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": (
                        "Username already exists. "
                        "Please choose another username."
                    )
                }
            )

        # ==========================================
        # CHECK USER EMAIL
        # ==========================================

        if email and User.objects.filter(
            email=email
        ).exists():

            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": (
                        "Email address is already registered. "
                        "Please use another email."
                    )
                }
            )

        # ==========================================
        # CHECK APPLICANT EMAIL
        # ==========================================

        if email and Applicant.objects.filter(
            email=email
        ).exists():

            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": (
                        "Email address is already registered. "
                        "Please use another email."
                    )
                }
            )

        # ==========================================
        # CHECK PHONE NUMBER
        # ==========================================

        if phone_number and Applicant.objects.filter(
            phone_number=phone_number
        ).exists():

            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": (
                        "Phone number is already registered. "
                        "Please use another phone number."
                    )
                }
            )

        # ==========================================
        # VALIDATE PHONE NUMBER
        # ==========================================

        if not phone_number.startswith("09"):

            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": (
                        "Please enter a valid Philippine "
                        "mobile number starting with 09."
                    )
                }
            )

        if len(phone_number) != 11:

            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": (
                        "Mobile number must contain "
                        "11 digits."
                    )
                }
            )

        # ==========================================
        # VALIDATE SKILLS
        # ==========================================

        if not skills:

            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": (
                        "Please enter at least one skill "
                        "to help us recommend suitable jobs."
                    )
                }
            )

        # ==========================================
        # FORMAT PHONE FOR IPROG
        # ==========================================

        formatted_phone = format_ph_mobile(
            phone_number
        )

        # ==========================================
        # GENERATE OTP
        # ==========================================

        otp_code = str(
            random.randint(
                100000,
                999999
            )
        )

        # ==========================================
        # OTP EXPIRATION
        # 5 MINUTES
        # ==========================================

        expires_at = (
            timezone.now()
            + timedelta(minutes=5)
        )

        # ==========================================
        # DELETE OLD TEMPORARY REGISTRATION
        # ==========================================

        ApplicantRegistrationOTP.objects.filter(
            username=username
        ).delete()

        ApplicantRegistrationOTP.objects.filter(
            phone_number=phone_number
        ).delete()

        # ==========================================
        # HASH PASSWORD
        # ==========================================

        hashed_password = make_password(
            password
        )

        # ==========================================
        # CREATE TEMPORARY REGISTRATION
        # ==========================================

        registration = ApplicantRegistrationOTP.objects.create(

            username=username,

            email=email,

            phone_number=phone_number,

            first_name=first_name,

            last_name=last_name,

            middle_name=middle_name,

            skills=skills,

            password=hashed_password,

            resume=resume,

            cover_letter=cover_letter,

            otp_code=otp_code,

            expires_at=expires_at,
        )

        # ==========================================
        # SMS MESSAGE
        # ==========================================

        message = (
            "PESO Pio Duran Job Portal: "
            f"Your verification code is {otp_code}. "
            "This code will expire in 5 minutes."
        )

        # ==========================================
        # SEND SMS
        # ==========================================

        try:

            response = send_iprog_sms(
                formatted_phone,
                message
            )

            # ======================================
            # CHECK IPROG RESPONSE
            # ======================================

            if response.status_code not in [200, 201]:

                print(
                    "IPROG ERROR:",
                    response.status_code,
                    response.text
                )

                registration.delete()

                return render(
                    request,
                    "pages/register_applicant.html",
                    {
                        "error": (
                            "Unable to send verification "
                            "code. Please try again."
                        )
                    }
                )

        except Exception as e:

            print(
                "IPROG SMS ERROR:",
                str(e)
            )

            registration.delete()

            return render(
                request,
                "pages/register_applicant.html",
                {
                    "error": (
                        "Unable to send verification "
                        "code. Please try again later."
                    )
                }
            )

        # ==========================================
        # SAVE REGISTRATION ID IN SESSION
        # ==========================================

        request.session[
            "applicant_registration_id"
        ] = registration.id

        # ==========================================
        # REDIRECT TO OTP PAGE
        # ==========================================

        return redirect(
            "verify-applicant-registration"
        )

    # ==============================================
    # GET REQUEST
    # ==============================================

    return render(
        request,
        "pages/register_applicant.html"
    )

def verify_applicant_registration(request):

    # ==========================================
    # GET REGISTRATION ID FROM SESSION
    # ==========================================

    registration_id = request.session.get(
        "applicant_registration_id"
    )

    # ==========================================
    # NO REGISTRATION
    # ==========================================

    if not registration_id:

        return redirect(
            "applicant-registration"
        )

    # ==========================================
    # GET TEMPORARY REGISTRATION
    # ==========================================

    try:

        registration = ApplicantRegistrationOTP.objects.get(
            id=registration_id
        )

    except ApplicantRegistrationOTP.DoesNotExist:

        request.session.pop(
            "applicant_registration_id",
            None
        )

        return redirect(
            "applicant-registration"
        )

    # ==========================================
    # CHECK EXPIRATION
    # ==========================================

    if registration.is_expired():

        registration.delete()

        request.session.pop(
            "applicant_registration_id",
            None
        )

        return render(
            request,
            "pages/verify_applicant.html",
            {
                "error": (
                    "Your verification code has expired. "
                    "Please register again."
                )
            }
        )

    # ==========================================
    # VERIFY OTP
    # ==========================================

    if request.method == "POST":

        otp = request.POST.get(
            "otp",
            ""
        ).strip()

        # ======================================
        # CHECK OTP
        # ======================================

        if otp != registration.otp_code:

            return render(
                request,
                "pages/verify_applicant.html",
                {
                    "error": (
                        "Invalid verification code. "
                        "Please try again."
                    )
                }
            )

        # ==========================================
        # CREATE USER
        # ==========================================

        user = User(
            username=registration.username,
            email=registration.email,
            password=registration.password,
        )

        # ==========================================
        # SET ROLE
        # ==========================================

        user.role = "applicant"

        user.save()

        # ==========================================
        # CREATE APPLICANT
        # ==========================================

        Applicant.objects.create(

            user=user,

            first_name=registration.first_name,

            last_name=registration.last_name,

            middle_name=registration.middle_name,

            email=registration.email,

            phone_number=registration.phone_number,

            resume=registration.resume,

            cover_letter=registration.cover_letter,
        )

        # ==========================================
        # MARK VERIFIED
        # ==========================================

        registration.is_verified = True

        registration.save(
            update_fields=[
                "is_verified"
            ]
        )

        # ==========================================
        # DELETE TEMPORARY REGISTRATION
        # ==========================================

        registration.delete()

        # ==========================================
        # CLEAR SESSION
        # ==========================================

        request.session.pop(
            "applicant_registration_id",
            None
        )

        # ==========================================
        # REDIRECT TO LOGIN
        # ==========================================

        return redirect(
            "login-user"
        )

    # ==========================================
    # DISPLAY OTP PAGE
    # ==========================================

    return render(
        request,
        "pages/verify_applicant.html"
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

    # =========================================================
    # APPROVED JOBS
    # =========================================================

    job = JobPost.objects.filter(
        status="approved"
    ).order_by("-created_at")


    # =========================================================
    # DEFAULT RECOMMENDATIONS
    # =========================================================

    recommended_jobs = []


    # =========================================================
    # GET APPLICANT PROFILE
    # =========================================================

    applicant = getattr(
        request.user,
        "applicant_profile",
        None
    )


    # =========================================================
    # SKILL-BASED RECOMMENDATIONS
    # =========================================================

    if applicant and applicant.skills:

        for current_job in job:

            score, matched_skills = (
                get_job_recommendation(
                    current_job,
                    applicant.skills
                )
            )

            # Only recommend jobs with
            # at least one matching skill
            if score > 0:

                recommended_jobs.append({
                    "job": current_job,
                    "score": score,
                    "matched_skills": matched_skills,
                })


        # Highest matching jobs first
        recommended_jobs.sort(
            key=lambda item: (
                item["score"],
                item["job"].created_at
            ),
            reverse=True
        )


        # Show only the top 5 recommendations
        recommended_jobs = recommended_jobs[:5]


    # =========================================================
    # RENDER
    # =========================================================

    return render(
        request,
        "pages/browse_job.html",
        {
            "job": job,
            "recommended_jobs": recommended_jobs,
        }
    )

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

    application = get_object_or_404(
        JobApplication,
        id=id
    )

    # ==========================================
    # ONLY THE EMPLOYER WHO OWNS THE JOB
    # CAN UPDATE THE APPLICATION
    # ==========================================

    if application.job.employer != request.user.employer:

        return redirect(
            "applicants-list"
        )

    # ==========================================
    # ONLY PROCESS POST REQUEST
    # ==========================================

    if request.method == "POST":

        new_status = request.POST.get(
            "status"
        )

        # ==========================================
        # VALID STATUS VALUES
        # ==========================================

        if new_status in [
            "pending",
            "reviewing",
            "shortlisted",
            "accepted",
            "rejected",
        ]:

            # ==========================================
            # ONLY PROCEED IF STATUS CHANGED
            # ==========================================

            if application.status != new_status:

                # ======================================
                # UPDATE APPLICATION STATUS
                # ======================================

                application.status = new_status

                application.save()

                # ======================================
                # GET APPLICANT PHONE NUMBER
                # ======================================

                phone = application.applicant.phone_number

                # ======================================
                # FORMAT PHILIPPINE MOBILE NUMBER
                # 0917xxxxxxx
                #       ↓
                # 63917xxxxxxx
                # ======================================

                phone = format_ph_mobile(
                    phone
                )

                # ======================================
                # PENDING
                # ======================================

                if application.status == "pending":

                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"Your application for the position of "
                        f"{application.job.title} at "
                        f"{application.job.employer.company_name} "
                        f"has been successfully received.\n\n"
                        f"Our recruitment team will review your "
                        f"application, and you will be notified once "
                        f"there are updates.\n\n"
                        f"Thank you for your interest in joining "
                        f"our organization.\n\n"
                        f"{application.job.employer.company_name}"
                    )

                # ======================================
                # REVIEWING
                # ======================================

                elif application.status == "reviewing":

                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"We would like to inform you that your "
                        f"application for the position of "
                        f"{application.job.title} at "
                        f"{application.job.employer.company_name} "
                        f"is currently under review.\n\n"
                        f"We appreciate your patience and will keep "
                        f"you informed of any further developments.\n\n"
                        f"Thank you.\n"
                        f"{application.job.employer.company_name}"
                    )

                # ======================================
                # SHORTLISTED
                # ======================================

                elif application.status == "shortlisted":

                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"Congratulations! You have been shortlisted "
                        f"for the position of "
                        f"{application.job.title} at "
                        f"{application.job.employer.company_name}.\n\n"
                        f"Our Human Resources team will contact you "
                        f"soon regarding the next stage of the "
                        f"recruitment process.\n\n"
                        f"Thank you, and we look forward to "
                        f"speaking with you.\n\n"
                        f"{application.job.employer.company_name}"
                    )

                # ======================================
                # ACCEPTED
                # ======================================

                elif application.status == "accepted":

                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"Congratulations! We are pleased to inform "
                        f"you that you have been selected for the "
                        f"position of {application.job.title} at "
                        f"{application.job.employer.company_name}.\n\n"
                        f"Our Human Resources team will contact you "
                        f"shortly with further instructions regarding "
                        f"your employment.\n\n"
                        f"Welcome to the team, and we wish you "
                        f"every success.\n\n"
                        f"Sincerely,\n"
                        f"{application.job.employer.company_name}"
                    )

                # ======================================
                # REJECTED
                # ======================================

                elif application.status == "rejected":

                    message = (
                        f"Dear {application.applicant.first_name},\n\n"
                        f"Thank you for your interest in the "
                        f"{application.job.title} position at "
                        f"{application.job.employer.company_name}.\n\n"
                        f"After careful evaluation, we regret to "
                        f"inform you that you have not been selected "
                        f"for this opportunity.\n\n"
                        f"We sincerely appreciate the time and effort "
                        f"you invested in your application and "
                        f"encourage you to apply for future "
                        f"opportunities with us.\n\n"
                        f"We wish you success in your future career.\n\n"
                        f"Sincerely,\n"
                        f"{application.job.employer.company_name}"
                    )

                # ======================================
                # SEND SMS THROUGH IPROG
                # ======================================

                try:

                    response = send_iprog_sms(
                        phone,
                        message
                    )

                    # ==================================
                    # LOG IPROG RESPONSE
                    # ==================================

                    if response.status_code not in [
                        200,
                        201
                    ]:

                        print(
                            "IPROG SMS ERROR:",
                            response.status_code,
                            response.text
                        )

                    else:

                        print(
                            "IPROG SMS SENT:",
                            response.status_code,
                            response.text
                        )

                except Exception as e:

                    print(
                        "IPROG SMS ERROR:",
                        str(e)
                    )

    # ==========================================
    # RETURN TO APPLICANTS
    # ==========================================

    return redirect(
        "applicants"
    )


@login_required(login_url="login_user")
def import_job_list(request):

    if request.method != "POST":
        return redirect("job-list")

    uploaded_file = request.FILES.get("job_file")

    if not uploaded_file:
        messages.error(request, "Please select a CSV file.")
        return redirect("job-list")

    # Only CSV files
    if not uploaded_file.name.lower().endswith(".csv"):
        messages.error(request, "Only CSV files are allowed.")
        return redirect("job-list")

    try:
        # Read uploaded CSV
        file_data = uploaded_file.read().decode("utf-8-sig")

        reader = csv.DictReader(
            io.StringIO(file_data)
        )

        # Required columns
        required_columns = {
            "title",
            "description",
            "qualifications",
            "responsibilities",
            "salary",
            "location",
            "job_type",
            "vacancies",
            "deadline",
        }

        csv_columns = set(reader.fieldnames or [])

        missing_columns = required_columns - csv_columns

        if missing_columns:
            messages.error(
                request,
                "Missing CSV columns: "
                + ", ".join(sorted(missing_columns))
            )

            return redirect("job-list")

        # Valid JobPost job_type values
        valid_job_types = {
            "full_time",
            "part_time",
            "contract",
            "internship",
            "temporary",
        }

        imported_count = 0
        skipped_count = 0

        with transaction.atomic():

            for row_number, row in enumerate(reader, start=2):

                try:

                    # ==========================================
                    # TEXT FIELDS
                    # ==========================================

                    title = row.get(
                        "title",
                        ""
                    ).strip()

                    description = row.get(
                        "description",
                        ""
                    ).strip()

                    qualifications = row.get(
                        "qualifications",
                        ""
                    ).strip()

                    responsibilities = row.get(
                        "responsibilities",
                        ""
                    ).strip()

                    location = row.get(
                        "location",
                        ""
                    ).strip()


                    # ==========================================
                    # REQUIRED VALIDATION
                    # ==========================================

                    if not title:
                        raise ValueError(
                            "Title is required."
                        )

                    if not description:
                        raise ValueError(
                            "Description is required."
                        )

                    if not qualifications:
                        raise ValueError(
                            "Qualifications are required."
                        )

                    if not location:
                        raise ValueError(
                            "Location is required."
                        )


                    # ==========================================
                    # JOB TYPE
                    # ==========================================

                    job_type = row.get(
                        "job_type",
                        "full_time"
                    ).strip().lower()

                    if job_type not in valid_job_types:

                        raise ValueError(
                            f"Invalid job type '{job_type}'. "
                            "Allowed values: "
                            "full_time, part_time, contract, "
                            "internship, temporary."
                        )


                    # ==========================================
                    # VACANCIES
                    # ==========================================

                    vacancies_value = row.get(
                        "vacancies",
                        "1"
                    ).strip()

                    try:

                        vacancies = int(
                            vacancies_value
                        )

                    except (ValueError, TypeError):

                        raise ValueError(
                            "Vacancies must be a whole number."
                        )

                    if vacancies < 1:

                        raise ValueError(
                            "Vacancies must be at least 1."
                        )


                    # ==========================================
                    # SALARY
                    # ==========================================

                    salary_value = row.get(
                        "salary",
                        ""
                    ).strip()

                    salary = None

                    if salary_value:

                        # Remove peso sign and commas
                        salary_value = (
                            salary_value
                            .replace("₱", "")
                            .replace(",", "")
                            .strip()
                        )

                        try:

                            salary = Decimal(
                                salary_value
                            )

                        except InvalidOperation:

                            raise ValueError(
                                "Salary must be a valid number."
                            )

                        if salary < 0:

                            raise ValueError(
                                "Salary cannot be negative."
                            )


                    # ==========================================
                    # DEADLINE
                    # ==========================================

                    deadline_value = row.get(
                        "deadline",
                        ""
                    ).strip()

                    if not deadline_value:

                        raise ValueError(
                            "Deadline is required."
                        )

                    try:

                        deadline = datetime.strptime(
                            deadline_value,
                            "%Y-%m-%d"
                        ).date()

                    except ValueError:

                        raise ValueError(
                            "Deadline must use YYYY-MM-DD format."
                        )


                    # ==========================================
                    # CREATE JOB POST
                    # ==========================================

                    JobPost.objects.create(

                        employer=request.user.employer,

                        title=title,

                        description=description,

                        qualifications=qualifications,

                        responsibilities=responsibilities,

                        salary=salary,

                        location=location,

                        job_type=job_type,

                        vacancies=vacancies,

                        deadline=deadline,

                        # Always require admin approval
                        status="pending",

                    )

                    imported_count += 1


                except Exception as row_error:

                    skipped_count += 1

                    messages.warning(
                        request,
                        f"Row {row_number} skipped: {row_error}"
                    )


        # ==========================================
        # SUCCESS / WARNING MESSAGES
        # ==========================================

        if imported_count > 0:

            messages.success(
                request,
                f"{imported_count} job post(s) imported successfully."
            )

        if skipped_count > 0:

            messages.warning(
                request,
                f"{skipped_count} row(s) skipped because of invalid data."
            )


    except UnicodeDecodeError:

        messages.error(
            request,
            "Unable to read the CSV file. "
            "Please save the CSV using UTF-8 encoding."
        )


    except Exception as e:

        messages.error(
            request,
            f"Unable to import job list: {str(e)}"
        )


    return redirect("job-list")