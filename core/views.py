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

    employer.is_active = not employer.is_active
    employer.save()

    if employer.is_active:
        messages.success(request, f"{employer.company_name} has been activated.")
    else:
        messages.warning(request, f"{employer.company_name} has been suspended.")

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

    # Allow only admins
    if not request.user.is_superuser and request.user.role != "admin":
        messages.error(request, "You are not authorized to approve job posts.")
        return redirect("job-post-list")

    if request.method == "POST":
        job.status = "approved"      
        job.is_approved = True      
        job.save()

        messages.success(request, "Job post has been approved and published.")
        return redirect("job-post-list")

    return render(request, "components/approved_job.html", {
        "job": job
    })

@login_required(login_url="login_user")
@require_POST
def delete_job(request, id):
    job = get_object_or_404(JobPost, id=id)

    title = job.title
    company = job.employer.company_name

    job.delete()

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