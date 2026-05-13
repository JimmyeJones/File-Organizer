from django.contrib import admin

from .models import Meeting, PresentationSlot


class PresentationSlotInline(admin.TabularInline):
    model = PresentationSlot
    extra = 1
    fields = ("topic", "description", "presenter", "claimed_at")
    readonly_fields = ("claimed_at",)
    autocomplete_fields = ("presenter",)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "time", "location", "is_published", "slot_count")
    list_filter = ("is_published", "date")
    search_fields = ("title", "location")
    date_hierarchy = "date"
    inlines = [PresentationSlotInline]

    def slot_count(self, obj):
        return obj.slots.count()
    slot_count.short_description = "Slots"


@admin.register(PresentationSlot)
class PresentationSlotAdmin(admin.ModelAdmin):
    list_display = ("meeting", "topic", "presenter", "claimed_at")
    list_filter = ("meeting",)
    search_fields = ("topic", "presenter__username", "presenter__callsign")
    autocomplete_fields = ("presenter",)
