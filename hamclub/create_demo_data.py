"""
Run with: python manage.py shell < create_demo_data.py

Creates a superuser (admin / admin123) and sample content for first-time setup.
"""
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hamclub.settings")
django.setup()

from django.utils import timezone
from accounts.models import Member
from events.models import Meeting, PresentationSlot
from pages.models import Page

# Superuser
if not Member.objects.filter(username="admin").exists():
    admin = Member.objects.create_superuser(
        username="admin",
        password="admin123",
        email="admin@hamclub.example.com",
        callsign="W1ABC",
        first_name="Club",
        last_name="Admin",
        is_approved=True,
    )
    print("Created superuser: admin / admin123")

# Home page
if not Page.objects.filter(slug="home").exists():
    Page.objects.create(
        title="Home",
        slug="home",
        content=(
            "<h2>Welcome to the HAM Radio Club</h2>"
            "<p>We are a group of amateur radio enthusiasts who meet monthly to share knowledge, "
            "discuss projects, and support our community.</p>"
            "<p>All licensed operators are welcome. Visitors are always encouraged to attend a meeting before joining.</p>"
        ),
    )
    print("Created home page")

# About page
if not Page.objects.filter(slug="about").exists():
    Page.objects.create(
        title="About",
        slug="about",
        content=(
            "<h2>About the Club</h2>"
            "<p>Founded in 1970, we hold monthly meetings on the <strong>second Tuesday of each month</strong> "
            "at the Community Center, 7:00 PM.</p>"
            "<p>We operate a <strong>2m/70cm repeater</strong> accessible to all licensed amateurs in the area.</p>"
            "<h3>Contact</h3>"
            "<p>Email: <a href='mailto:info@hamclub.example.com'>info@hamclub.example.com</a></p>"
        ),
    )
    print("Created about page")

# Sample meeting
today = timezone.now().date()
import datetime
next_tuesday = today + datetime.timedelta(days=(1 - today.weekday() + 7) % 7 or 7)
if not Meeting.objects.exists():
    meeting = Meeting.objects.create(
        title="Monthly Club Meeting",
        date=next_tuesday,
        time=datetime.time(19, 0),
        location="Community Center, Room 12",
        description="Our regular monthly meeting. All members and visitors welcome!",
    )
    PresentationSlot.objects.create(meeting=meeting)
    PresentationSlot.objects.create(meeting=meeting)
    print(f"Created sample meeting on {next_tuesday}")

print("Done.")
