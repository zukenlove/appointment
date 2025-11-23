from datetime import datetime, timedelta, time, date
from .models import TimeSlot, Day,Appointment, Business
from django.db import transaction
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from functools import wraps




def generate_time_slots(day, start_time, end_time, interval_minutes=30, breaks=None):
    """
    Generate TimeSlot objects for a given Day.
    
    Args:
        day (Day): Day instance
        start_time (datetime.time): start of the workday
        end_time (datetime.time): end of the workday
        interval_minutes (int): slot length in minutes
        breaks (list of tuples): [(break_start_time, break_end_time), ...]
    
    Returns:
        int: number of slots created
    """
    slots_created = 0
    current = datetime.combine(day.date, start_time)
    end = datetime.combine(day.date, end_time)

    breaks = breaks or []

    while current + timedelta(minutes=interval_minutes) <= end:
        slot_start = current.time()
        slot_end_dt = current + timedelta(minutes=interval_minutes)
        slot_end = slot_end_dt.time()

        # Skip if slot overlaps with any break
        if any(slot_start < b_end and slot_end > b_start for b_start, b_end in breaks):
            current = slot_end_dt
            continue

        # Avoid duplicate slots
        if not TimeSlot.objects.filter(day=day, start=slot_start, end=slot_end).exists():
            TimeSlot.objects.create(day=day, start=slot_start, end=slot_end, is_booked=False)
            slots_created += 1

        current = slot_end_dt

    return slots_created


def generate_week(business, start_date, end_date, start_time, end_time, interval, breaks=None):
    """
    Generate slots for all weekdays in a week.
    Skips Saturday and Sunday.
    """
    current = max(start_date, date.today())
    days_created = 0
    slots_created = 0

    while current <= end_date:
        if current.weekday() < 5:  # Monday=0 ... Friday=4
            day, created = Day.objects.get_or_create(date=current, business=business)
            if created:
                days_created += 1
            slots_created += generate_time_slots(day, start_time, end_time, interval, breaks)
        current += timedelta(days=1)

    return days_created, slots_created


def generate_month(business, year, month, start_time, end_time, interval, breaks=None):
    """
    Generate slots for all weekdays in a month.
    Skips Saturday and Sunday.
    """
    from calendar import monthrange
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    current = first_day
    days_created = 0
    slots_created = 0

    while current <= last_day:
        if current.weekday() < 5:  # skip weekends
            day, created = Day.objects.get_or_create(date=current, business=business)
            if created:
                days_created += 1
            slots_created += generate_time_slots(day, start_time, end_time, interval, breaks)
        current += timedelta(days=1)

    return days_created, slots_created

def regenerate_slots(day, start_time, end_time, interval_minutes=30, breaks=None):
    """
    Regenerate time slots for a Day.
    Preserves already booked slots.
    
    day: Day instance
    start_time, end_time: datetime.time objects
    interval_minutes: int
    breaks: list of (start, end) times to skip
    """
    # Delete all unbooked slots
    TimeSlot.objects.filter(day=day, is_booked=False).delete()
    
    # Generate new slots
    return generate_time_slots(day, start_time, end_time, interval_minutes, breaks=breaks)



def book_slot(user, slot_id):
    with transaction.atomic():
        slot = TimeSlot.objects.select_for_update().get(id=slot_id)

        if slot.is_booked:
            raise ValueError("This slot is already booked.")

        if Appointment.objects.filter(user=user, slot__day=slot.day).exists():
            raise ValueError("You already have a booking on this day for this business.")

        slot.is_booked = True
        slot.save()

        appt = Appointment.objects.create(user=user, slot=slot, business=slot.day.business)

        return appt


def generate_time_slots(day, start_time, end_time, interval, breaks=None):
    """
    Generates TimeSlot objects for a given Day.
    
    Arguments:
    - day: Day instance
    - start_time: datetime.time, starting time of the day
    - end_time: datetime.time, ending time of the day
    - interval: int, slot length in minutes
    - breaks: list of tuples [(start_time, end_time), ...] for break periods
    
    Returns:
    - count: number of slots created
    """
    if breaks is None:
        breaks = []

    slots_created = 0

    # Convert start and end times to datetime objects on the same date
    current = datetime.combine(day.date, start_time)
    end_datetime = datetime.combine(day.date, end_time)

    while current + timedelta(minutes=interval) <= end_datetime:
        slot_start = current.time()
        slot_end = (current + timedelta(minutes=interval)).time()

        # Skip if slot falls into a break
        if any(b_start <= slot_start < b_end or b_start < slot_end <= b_end for b_start, b_end in breaks):
            current += timedelta(minutes=interval)
            continue

        # Prevent duplicate slots
        if not TimeSlot.objects.filter(day=day, start=slot_start, end=slot_end).exists():
            TimeSlot.objects.create(day=day, start=slot_start, end=slot_end)
            slots_created += 1

        current += timedelta(minutes=interval)

    return slots_created


def owner_required(view_func):
    """Custom decorator to allow only business owners."""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('calendar:login')
        if request.user.profile.role != 'owner':
            messages.error(request, "Only business owners can access this page.")
            return redirect('calendar:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_or_owner_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Try to get business directly
        business_id = kwargs.get('business_id')
        if business_id:
            business = get_object_or_404(Business, id=business_id)
        else:
            # Fall back to day_id -> find the related business
            day_id = kwargs.get('day_id')
            if day_id:
                day = get_object_or_404(Day, id=day_id)
                business = day.business
            else:
                messages.error(request, "Business context not found.")
                return redirect('calendar:dashboard')

        if request.user != business.owner and request.user not in business.staff.all():
            messages.error(request, "You do not have permission to access this page.")
            return redirect('calendar:dashboard')

        return view_func(request, *args, **kwargs)

    return wrapper

