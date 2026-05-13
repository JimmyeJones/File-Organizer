from django.conf import settings
from django.db import models
from django.utils import timezone


class Meeting(models.Model):
    title = models.CharField(max_length=200)
    date = models.DateField()
    time = models.TimeField()
    location = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    recording = models.FileField(upload_to="recordings/", blank=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["-date", "-time"]

    def __str__(self):
        return f"{self.title} — {self.date}"

    @property
    def is_past(self):
        return self.date < timezone.now().date()


class PresentationSlot(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="slots")
    topic = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    presenter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="presentation_slots",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["meeting__date", "id"]

    def __str__(self):
        if self.presenter:
            return f"{self.meeting} — {self.topic or 'TBD'} by {self.presenter}"
        return f"{self.meeting} — open slot"

    @property
    def is_claimed(self):
        return self.presenter is not None
