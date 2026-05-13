from django.db import models


class Location(models.Model):
    CATEGORY_CHOICES = [
        ("meeting", "Meeting Venue"),
        ("repeater", "Repeater Site"),
        ("event", "Event"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    description = models.TextField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def has_coords(self):
        return self.latitude is not None and self.longitude is not None
