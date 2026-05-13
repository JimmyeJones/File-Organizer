from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from .forms import RegistrationForm
from .models import Member


def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.is_active = False
            member.is_approved = False
            member.save()
            send_mail(
                subject="New membership application",
                message=(
                    f"A new member has registered: {member.get_full_name() or member.username} "
                    f"({member.callsign})\nEmail: {member.email}\n\n"
                    f"Approve at {settings.CLUB_ADMIN_EMAIL} or in the Django admin."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CLUB_ADMIN_EMAIL],
                fail_silently=True,
            )
            messages.success(request, "Registration received! An admin will review your application shortly.")
            return redirect("register_done")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


def register_done(request):
    return render(request, "accounts/register_done.html")


@login_required
def profile(request):
    return render(request, "accounts/profile.html")


def roster(request):
    members = Member.objects.filter(is_approved=True, is_active=True).order_by("last_name", "first_name")
    return render(request, "accounts/roster.html", {"members": members})
