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

@login_required(login_url="login_user")
def reports(request):
    context = {
        "total_employers": Employer.objects.count(),
        "active_employers": Employer.objects.filter(is_active=True).count(),
        "suspended_employers": Employer.objects.filter(is_active=False).count(),

        "total_applicants": Applicant.objects.count(),

        "total_jobs": JobPost.objects.count(),
        "approved_jobs": JobPost.objects.filter(status="approved").count(),
        "pending_jobs": JobPost.objects.filter(status="pending").count(),
        "rejected_jobs": JobPost.objects.filter(status="rejected").count(),

        "employers": Employer.objects.all(),
        "applicants": Applicant.objects.all(),
        "jobs": JobPost.objects.select_related("employer").all(),
    }

    return render(request, "pages/reports.html", context)


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