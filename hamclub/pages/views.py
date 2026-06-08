from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Page
from events.models import Meeting


def home(request):
    try:
        page = Page.objects.get(slug="home", is_published=True)
    except Page.DoesNotExist:
        page = None
    next_meeting = (
        Meeting.objects.filter(is_published=True, date__gte=timezone.now().date())
        .order_by("date", "time")
        .first()
    )
    return render(request, "pages/home.html", {"page": page, "next_meeting": next_meeting})


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, "pages/page_detail.html", {"page": page})
