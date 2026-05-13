from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ClaimSlotForm
from .models import Meeting, PresentationSlot


def meeting_list(request):
    today = timezone.now().date()
    upcoming = Meeting.objects.filter(is_published=True, date__gte=today).order_by("date", "time")
    past = Meeting.objects.filter(is_published=True, date__lt=today).order_by("-date", "-time")
    return render(request, "events/meeting_list.html", {"upcoming": upcoming, "past": past})


def meeting_detail(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk, is_published=True)
    return render(request, "events/meeting_detail.html", {"meeting": meeting})


@login_required
def recording(request, pk):
    if not request.user.is_approved:
        messages.warning(request, "Your membership is pending approval.")
        return redirect("meeting_detail", pk=pk)
    meeting = get_object_or_404(Meeting, pk=pk, is_published=True)
    if not meeting.recording:
        messages.info(request, "No recording is available for this meeting.")
        return redirect("meeting_detail", pk=pk)
    return render(request, "events/recording.html", {"meeting": meeting})


@login_required
def claim_slot(request, pk, slot_pk):
    if not request.user.is_approved:
        messages.warning(request, "Your membership is pending approval.")
        return redirect("meeting_detail", pk=pk)
    meeting = get_object_or_404(Meeting, pk=pk, is_published=True)
    slot = get_object_or_404(PresentationSlot, pk=slot_pk, meeting=meeting, presenter__isnull=True)

    if request.method == "POST":
        form = ClaimSlotForm(request.POST, instance=slot)
        if form.is_valid():
            slot = form.save(commit=False)
            slot.presenter = request.user
            slot.claimed_at = timezone.now()
            slot.save()
            send_mail(
                subject=f"Presentation slot claimed: {meeting.title}",
                message=(
                    f"{request.user} has claimed a slot at {meeting.title} ({meeting.date}).\n"
                    f"Topic: {slot.topic or 'TBD'}\n{slot.description}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CLUB_ADMIN_EMAIL],
                fail_silently=True,
            )
            messages.success(request, "You've claimed the slot! See you at the meeting.")
            return redirect("meeting_detail", pk=pk)
    else:
        form = ClaimSlotForm(instance=slot)
    return render(request, "events/claim_slot.html", {"meeting": meeting, "slot": slot, "form": form})
