import json

from django.shortcuts import render
from django.utils import timezone

from .models import Location
from events.models import Meeting


def map_view(request):
    pins = []

    for loc in Location.objects.filter(is_published=True, latitude__isnull=False, longitude__isnull=False):
        pins.append({
            "name": loc.name,
            "lat": float(loc.latitude),
            "lng": float(loc.longitude),
            "description": loc.description,
            "category": loc.get_category_display(),
            "url": "",
        })

    today = timezone.now().date()
    for meeting in Meeting.objects.filter(is_published=True, latitude__isnull=False, longitude__isnull=False):
        label = "[Upcoming] " if meeting.date >= today else "[Past] "
        pins.append({
            "name": label + meeting.title,
            "lat": float(meeting.latitude),
            "lng": float(meeting.longitude),
            "description": f"{meeting.date} at {meeting.time.strftime('%I:%M %p')} — {meeting.location}",
            "category": "Meeting",
            "url": f"/events/{meeting.pk}/",
        })

    return render(request, "locations/map.html", {"pins_json": json.dumps(pins), "pin_count": len(pins)})
