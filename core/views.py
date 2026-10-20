from django.shortcuts import render, redirect, get_object_or_404
from user.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from user.utils import create_default_admin
from django.contrib import messages
from employer.models import Employer, JobPost, JobApplication
from django.views.decorators.http import require_POST
from applicant.models import Applicant
from django.db.models import Count
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from datetime import datetime


def keep_alive(request):
    return JsonResponse({
        "status": "ok",
        "service": "Django API",
        "timestamp": timezone.now().isoformat(),
    })

def login_view(request):
    create_default_admin()

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            # Allow only admin users
            if user.role == "admin":
                login(request, user)
                return redirect("peso-dashboard") 
            else:
                messages.error(request, "Only administrators can log in.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return redirect('peso-login')

@login_required(login_url="login_user")
def peso_dashboard(request):

    context = {
        "total_employers": Employer.objects.count(),
        "active_applicants": Applicant.objects.count(),
        "open_jobs": JobPost.objects.filter(status="approved").count(),
        "pending_reviews": JobPost.objects.filter(status="pending").count(),

        "recent_employers": Employer.objects.order_by("-created_at")[:3],
        "recent_applicants": Applicant.objects.order_by("-user__date_joined")[:3],
        "recent_jobs": JobPost.objects.select_related("employer").order_by("-created_at")[:4],
    }

    return render(request, "pages/dashboard.html", context)

@login_required(login_url="login_user")
def employer_list(request):
    employer = Employer.objects.all()
    return render(request, 'pages/employers.html', {"employer": employer})

@login_required(login_url="login_user")
def employer_detail(request, id):
    employer = get_object_or_404(Employer, id=id)

    return render(request, "pages/employer_detail.html", {
        "employer": employer
    })

@login_required(login_url="login_user")
def suspend_employer(request, id):

    employer = get_object_or_404(Employer, id=id)

    # =========================================================
    # GET EMAIL FROM RELATED USER ACCOUNT
    # =========================================================

    employer_email = employer.employer.email

    # =========================================================
    # TOGGLE EMPLOYER STATUS
    # =========================================================

    employer.is_active = not employer.is_active
    employer.save()

    # =========================================================
    # EMPLOYER ACTIVATED
    # =========================================================

    if employer.is_active:

        subject = "Your Employer Account Has Been Activated"

        message = f"""
Hello {employer.company_name},

Good news!

Your employer account has been successfully activated.

You can now log in to your employer account and continue using the PESO system.

Company:
{employer.company_name}

Your account is now active and you may access the employer features available to your account.

Thank you.

PESO Pio Duran
Public Employment Service Office
"""

        if employer_email:

            try:

                send_mail(
                    subject,
                    message,
                    None,
                    [employer_email],
                    fail_silently=False,
                )

                messages.success(
                    request,
                    f"{employer.company_name} has been activated and an activation email has been sent."
                )

            except Exception as e:

                messages.warning(
                    request,
                    f"{employer.company_name} has been activated, but the activation email could not be sent."
                )

        else:

            messages.success(
                request,
                f"{employer.company_name} has been activated."
            )

    # =========================================================
    # EMPLOYER SUSPENDED
    # =========================================================

    else:

        subject = "Your Employer Account Has Been Suspended"

        message = f"""
Hello {employer.company_name},

This is to inform you that your employer account has been suspended.

Company:
{employer.company_name}

Your account is currently inactive and you will not be able to access the employer features of the PESO system while your account is suspended.

If you believe this suspension was made in error or you need assistance, please contact the PESO Pio Duran office.

Thank you.

PESO Pio Duran
Public Employment Service Office
"""

        if employer_email:

            try:

                send_mail(
                    subject,
                    message,
                    None,
                    [employer_email],
                    fail_silently=False,
                )

                messages.warning(
                    request,
                    f"{employer.company_name} has been suspended and a suspension email has been sent."
                )

            except Exception as e:

                messages.warning(
                    request,
                    f"{employer.company_name} has been suspended, but the suspension email could not be sent."
                )

        else:

            messages.warning(
                request,
                f"{employer.company_name} has been suspended."
            )

    return redirect("employer-list")

@login_required(login_url="login_user")
def delete_employer(request, id):
    employer = get_object_or_404(Employer, id=id)

    company_name = employer.company_name

    # Delete the associated user (this also deletes the Employer
    # because of the OneToOneField with on_delete=models.CASCADE)
    employer.employer.delete()

    messages.success(request, f"{company_name} has been deleted.")

    return redirect("employer-list")

@login_required(login_url="login_user")
def job_list(request):
    jobs = JobPost.objects.all()
    return render(request, "pages/job_post.html", {"jobs":jobs})

@login_required(login_url="login_user")
def view_job(request, id):
    job = get_object_or_404(JobPost, id=id)

    return render(request, "pages/view_job.html", {
        "job": job
    })

@login_required(login_url="login_user")
def approve_job(request, id):

    job = get_object_or_404(JobPost, id=id)

    # =========================================================
    # ALLOW ONLY ADMINS
    # =========================================================

    if not request.user.is_superuser and request.user.role != "admin":

        messages.error(
            request,
            "You are not authorized to approve job posts."
        )

        return redirect("job-post-list")


    # =========================================================
    # APPROVE JOB
    # =========================================================

    if request.method == "POST":

        job.status = "approved"
        job.approved_at = timezone.now()
        job.save()


        # =====================================================
        # GET EMPLOYER EMAIL
        # =====================================================

        employer_email = job.employer.employer.email


        # =====================================================
        # SEND APPROVAL EMAIL
        # =====================================================

        if employer_email:

            subject = "Your Job Post Has Been Approved"

            message = f"""
Hello {job.employer.company_name},

Good news!

Your job posting has been approved by the PESO Pio Duran administrator.

JOB DETAILS
----------------------------------------

Job Title:
{job.title}

Job Type:
{job.get_job_type_display()}

Location:
{job.location}

Vacancies:
{job.vacancies}

Salary:
{job.salary_display}

Application Deadline:
{job.deadline.strftime("%B %d, %Y")}

----------------------------------------

Your job post is now approved and published on the PESO system.

Applicants can now view your job posting and submit applications.

Please log in to your employer account to monitor your job posting and applications.

Thank you for using the PESO Pio Duran Job Portal.

PESO Pio Duran
Public Employment Service Office
"""


            try:

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [employer_email],
                    fail_silently=False,
                )

                messages.success(
                    request,
                    f"Job post '{job.title}' has been approved and published. "
                    f"An approval email has been sent to the employer."
                )

            except Exception:

                messages.warning(
                    request,
                    f"Job post '{job.title}' has been approved and published, "
                    f"but the approval email could not be sent."
                )

        else:

            messages.success(
                request,
                f"Job post '{job.title}' has been approved and published."
            )


        return redirect("job-post-list")


    # =========================================================
    # APPROVAL CONFIRMATION PAGE
    # =========================================================

    return render(
        request,
        "components/approved_job.html",
        {
            "job": job
        }
    )

@login_required(login_url="login_user")
@require_POST
def delete_job(request, id):

    # =========================================================
    # ADMIN ACCESS ONLY
    # =========================================================

    if not request.user.is_superuser and request.user.role != "admin":

        messages.error(
            request,
            "You are not authorized to delete job posts."
        )

        return redirect("job-list")


    # =========================================================
    # GET JOB
    # =========================================================

    job = get_object_or_404(
        JobPost.objects.select_related("employer"),
        id=id
    )


    # =========================================================
    # SAVE INFORMATION BEFORE DELETE
    # =========================================================

    title = job.title

    company = (
        job.employer.company_name
        if job.employer
        else "Unknown Company"
    )


    # =========================================================
    # DELETE
    # =========================================================

    job.delete()


    # =========================================================
    # SUCCESS MESSAGE
    # =========================================================

    messages.success(
        request,
        f'"{title}" from {company} has been deleted successfully.'
    )


    return redirect("job-list")

@login_required(login_url="login_user")
def applicant_list(request):
    applicants = Applicant.objects.select_related("user").all()

    return render(request, "pages/applicant_list.html", {
        "applicants": applicants
    })

def get_date_field(model, candidates):
    """
    Return the first valid date/datetime field path
    available on a model, including supported related fields.
    """
    for path in candidates:
        current_model = model
        valid = True

        for part in path.split("__"):
            try:
                field = current_model._meta.get_field(part)
            except Exception:
                valid = False
                break

            if field.is_relation and field.related_model:
                current_model = field.related_model
            elif part != path.split("__")[-1]:
                valid = False
                break

        if valid:
            return path

    return None


def filter_by_date(queryset, date_field, date_from, date_to):
    """
    Apply an inclusive date range to a queryset.
    The end date includes the entire selected day.
    """
    if not date_field:
        return queryset.none()

    filters = {}

    if date_from:
        filters[f"{date_field}__date__gte"] = date_from

    if date_to:
        filters[f"{date_field}__date__lte"] = date_to

    if filters:
        queryset = queryset.filter(**filters)

    return queryset


@login_required(login_url="login_user")
def reports(request):
    date_from = None
    date_to = None
    date_error = ""

    date_from_value = request.GET.get("date_from", "").strip()
    date_to_value = request.GET.get("date_to", "").strip()

    # Parse the dates submitted by the filter form.
    try:
        if date_from_value:
            date_from = datetime.strptime(
                date_from_value, "%Y-%m-%d"
            ).date()

        if date_to_value:
            date_to = datetime.strptime(
                date_to_value, "%Y-%m-%d"
            ).date()

    except ValueError:
        date_error = "Please enter valid dates."

    if (
        not date_error
        and date_from
        and date_to
        and date_from > date_to
    ):
        date_error = "The start date cannot be later than the end date."

    # Base querysets.
    employers = Employer.objects.all().order_by("-created_at")
    applicants = Applicant.objects.all()
    jobs = JobPost.objects.select_related(
        "employer"
    ).all().order_by("-created_at")

    # Identify the actual date fields available in each model.
    employer_date_field = get_date_field(
        Employer,
        [
            "created_at",
            "date_joined",
            "registered_at",
        ],
    )

    applicant_date_field = get_date_field(
        Applicant,
        [
            "created_at",
            "date_joined",
            "registered_at",
            "user__date_joined",
        ],
    )

    job_date_field = get_date_field(
        JobPost,
        [
            "created_at",
            "posted_at",
            "date_posted",
        ],
    )

    if not date_error and (date_from or date_to):
        # Filter each table independently using its own date field.
        employers = filter_by_date(
            employers,
            employer_date_field,
            date_from,
            date_to,
        )

        applicants = filter_by_date(
            applicants,
            applicant_date_field,
            date_from,
            date_to,
        )

        jobs = filter_by_date(
            jobs,
            job_date_field,
            date_from,
            date_to,
        )

        # Warn if a model has no recognized date field.
        missing_models = []

        if not employer_date_field:
            missing_models.append("Employer")

        if not applicant_date_field:
            missing_models.append("Applicant")

        if not job_date_field:
            missing_models.append("JobPost")

        if missing_models:
            date_error = (
                "Date filtering needs a valid date field for: "
                + ", ".join(missing_models)
                + ". Please check those models."
            )

    elif date_error:
        # Invalid date input: don't display misleading records.
        employers = employers.none()
        applicants = applicants.none()
        jobs = jobs.none()

    # Counts use the same filtered querysets as the tables.
    total_employers = employers.count()
    active_employers = employers.filter(is_active=True).count()
    suspended_employers = employers.filter(is_active=False).count()

    total_applicants = applicants.count()

    total_jobs = jobs.count()
    approved_jobs = jobs.filter(status="approved").count()
    pending_jobs = jobs.filter(status="pending").count()
    rejected_jobs = jobs.filter(status="rejected").count()

    context = {
        "total_employers": total_employers,
        "active_employers": active_employers,
        "suspended_employers": suspended_employers,
        "total_applicants": total_applicants,
        "total_jobs": total_jobs,
        "approved_jobs": approved_jobs,
        "pending_jobs": pending_jobs,
        "rejected_jobs": rejected_jobs,

        "employers": employers,
        "applicants": applicants,
        "jobs": jobs,

        "date_from": date_from_value,
        "date_to": date_to_value,
        "date_error": date_error,
        "report_generated": bool(date_from_value or date_to_value),
        "report_date": timezone.localtime().strftime(
            "%B %d, %Y %I:%M %p"
        ),
    }

    return render(
        request,
        "pages/reports.html",
        context,
    )



@login_required(login_url="login_user")
def delete_selected_applicants(request):

    if request.method != "POST":
        return redirect("applicants")

    applicant_ids = request.POST.getlist("applicant_ids")

    if not applicant_ids:
        messages.error(
            request,
            "Please select at least one applicant."
        )
        return redirect("applicants")

    try:
        with transaction.atomic():

            applicants = Applicant.objects.filter(
                id__in=applicant_ids
            ).select_related("user")

            deleted_count = applicants.count()

            users_to_delete = []

            for applicant in applicants:
                if applicant.user:
                    users_to_delete.append(applicant.user)

            # Delete applicant profiles
            applicants.delete()

            # Delete their associated user accounts
            for user in users_to_delete:
                user.delete()

        messages.success(
            request,
            f"{deleted_count} applicant(s) deleted successfully."
        )

    except Exception as e:

        messages.error(
            request,
            f"Unable to delete applicants: {str(e)}"
        )

    return redirect("applicants")