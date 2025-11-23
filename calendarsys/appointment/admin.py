from django.contrib import admin
from django.shortcuts import render, redirect
from datetime import date, time
from .utils import generate_time_slots, generate_week, generate_month, regenerate_slots


from .models import Day, TimeSlot, Appointment, Business
from .forms import SlotGenerationForm
from .utils import (
    generate_time_slots,
    generate_week,
    generate_month,
    regenerate_slots
)

from django.contrib import admin
from django.contrib.auth.models import User
from .models import Business


# Unregister original User admin and register new one
admin.site.unregister(User)


class TimeSlotInline(admin.TabularInline):
    model = TimeSlot
    extra = 0
    readonly_fields = ("is_booked",)
    fields = ("start", "end", "is_booked")


@admin.register(Day)
class DayAdmin(admin.ModelAdmin):
    list_display = ("date", "business_name")  # <-- updated
    inlines = [TimeSlotInline]

    # method to show business name in list_display
    def business_name(self, obj):
        return obj.business.name
    business_name.short_description = "Business"


    # -----------------------------------------
    # 1️⃣ Generate slots for selected days
    # -----------------------------------------
    def generate_slots_action(self, request, queryset):
        if "apply" in request.POST:
            form = SlotGenerationForm(request.POST)
            if form.is_valid():
                created_total = 0
                for day in queryset:
                    created_total += generate_time_slots(
                        day,
                        form.cleaned_data["start_time"],
                        form.cleaned_data["end_time"],
                        form.cleaned_data["interval_minutes"]
                    )
                self.message_user(request, f"Created {created_total} time slots.")
                return redirect(request.get_full_path())

        else:
            form = SlotGenerationForm()

        return render(request, "admin/slot_generation_form.html", {
            "form": form,
            "days": queryset,
            "title": "Generate Time Slots for Selected Days"
        })

    generate_slots_action.short_description = "Generate slots for selected days"

    # -----------------------------------------
    # 2️⃣ Generate week
    # -----------------------------------------
    def generate_week_action(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(request, "Select ONE day to generate a week.", "error")
            return

        day = queryset.first()

        days_created, slots_created = generate_week(
            business=day.business,
            start_date=day.date,
            start_time=time(9, 0),
            end_time=time(17, 0),
            interval_minutes=30,
            breaks=[(time(12, 0), time(13, 0))]
        )

        self.message_user(request, f"Week generated: {days_created} days, {slots_created} slots.")

    generate_week_action.short_description = "Generate whole week"

    # -----------------------------------------
    # 3️⃣ Generate month
    # -----------------------------------------
    def generate_month_action(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(request, "Select ONE day from the month.", "error")
            return

        day = queryset.first()

        days_created, slots_created = generate_month(
            business=day.business,
            year=day.date.year,
            month=day.date.month,
            start_time=time(9, 0),
            end_time=time(17, 0),
            interval_minutes=30,
            breaks=[(time(12, 0), time(13, 0))]
        )

        self.message_user(request, f"Month generated: {days_created} days, {slots_created} slots.")

    generate_month_action.short_description = "Generate whole month"

    # -----------------------------------------
    # 4️⃣ Regenerate slots (delete unused)
    # -----------------------------------------
    def regenerate_slots_action(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(request, "Select ONE day to regenerate.", "error")
            return

        day = queryset.first()

        created = regenerate_slots(
            day,
            start_time=time(9, 0),
            end_time=time(17, 0),
            interval_minutes=30,
            breaks=[(time(12, 0), time(13, 0))]
        )

        self.message_user(request, f"Regenerated: {created} new slots (booked slots preserved).")

    regenerate_slots_action.short_description = "Regenerate slots (keep booked ones)"


# Register the remaining models
admin.site.register(TimeSlot)
admin.site.register(Appointment)
admin.site.register(Business)
admin.site.register(User)


