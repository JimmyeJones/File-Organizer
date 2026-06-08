from django.contrib import admin

from .models import Location

LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"


class MapAdminMixin:
    """Injects the Leaflet map picker into any ModelAdmin that has latitude/longitude fields."""

    class Media:
        css = {"all": [LEAFLET_CSS]}
        js = [LEAFLET_JS, "locations/js/admin_map.js"]


@admin.register(Location)
class LocationAdmin(MapAdminMixin, admin.ModelAdmin):
    list_display = ("name", "category", "address", "has_coords", "is_published")
    list_filter = ("category", "is_published")
    search_fields = ("name", "address")
    fieldsets = (
        (None, {"fields": ("name", "category", "description", "is_published")}),
        ("Map pin", {"fields": ("address", "latitude", "longitude"),
                     "description": "Enter an address and press Enter to search, or click the map to place a pin."}),
    )
