from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Business, UserProfile, Day, TimeSlot, Appointment
from .forms import UserRegistrationForm, BusinessForm, CreateDayForm, SlotGenerationForm
from .utils import generate_time_slots, owner_required, staff_or_owner_required
from django.contrib.auth.models import User, Group
from .forms import CreateDayForm
from datetime import date




# -------------------------
# USER REGISTRATION
# -------------------------
def signup(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Account created for {user.username}!")
            return redirect('calendar:login')
    else:
        form = UserRegistrationForm()
    return render(request, 'appointment/signup.html', {'form': form})


# -------------------------
# BUSINESS CREATION
# -------------------------
@login_required
@owner_required
def create_business(request):
    if request.method == 'POST':
        form = BusinessForm(request.POST)
        if form.is_valid():
            business = form.save(commit=False)
            business.owner = request.user
            business.save()
            messages.success(request, f"Business '{business.name}' created successfully!")
            return redirect('calendar:dashboard')
    else:
        form = BusinessForm()
    return render(request, 'appointment/create_business.html', {'form': form})


# -------------------------
# DAY CREATION
# -------------------------
@login_required
def create_day(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    if request.user != business.owner:
        messages.error(request, "You do not have permission to add days to this business.")
        return redirect('calendar:dashboard')

    if request.method == 'POST':
        form = CreateDayForm(request.POST)
        if form.is_valid():
            day = form.save(commit=False)
            day.business = business
            day.save()
            messages.success(request, f"Day {day.date} added to {business.name}.")
            return redirect('calendar:business_detail', business_id=business.id)
    else:
        form = CreateDayForm()
    return render(request, 'appointment/create_day.html', {'form': form, 'business': business})


# -------------------------
# SLOT GENERATION
# -------------------------
@login_required
@staff_or_owner_required
def generate_slots(request, day_id):
    day = get_object_or_404(Day, id=day_id)
    if request.user != day.business.owner:
        messages.error(request, "You do not have permission to generate slots for this business.")
        return redirect('calendar:dashboard')

    if request.method == 'POST':
        form = SlotGenerationForm(request.POST)
        if form.is_valid():
            count = generate_time_slots(
                day=day,
                start_time=form.cleaned_data['start_time'],
                end_time=form.cleaned_data['end_time'],
                interval=form.cleaned_data['interval_minutes'],
                breaks=form.cleaned_data['breaks']
            )
            messages.success(request, f"{count} slots generated for {day.date}.")
            return redirect('calendar:day_detail', day_id=day.id)
    else:
        form = SlotGenerationForm()
    return render(request, 'appointment/slot_generation_form.html', {'form': form, 'day': day})


# -------------------------
# BOOKING APPOINTMENT
# -------------------------
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from .models import TimeSlot, Appointment

@login_required
def book_slot(request, slot_id):
    slot = get_object_or_404(TimeSlot, id=slot_id)
    profile = request.user.profile

    # Only clients can book
    if profile.role != 'client':
        messages.error(request, "Only clients can book appointments.")
        return redirect('calendar:dashboard')

    # Only one booking per day per client
    if Appointment.objects.filter(client=request.user, slot__day=slot.day).exists():
        messages.error(request, f"You already have a booking on {slot.day.date}.")
        return redirect('calendar:day_detail', day_id=slot.day.id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Concurrency-safe creation handled inside Appointment.save()
                Appointment.objects.create(client=request.user, slot=slot)
                messages.success(request, f"Slot booked: {slot.start}-{slot.end} on {slot.day.date}.")
            return redirect('calendar:day_detail', day_id=slot.day.id)
        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect('calendar:day_detail', day_id=slot.day.id)
        except Exception as e:
            messages.error(request, f"Error booking slot: {str(e)}")
            return redirect('calendar:day_detail', day_id=slot.day.id)

    # Render confirmation page
    return render(request, 'appointment/confirm_booking.html', {'slot': slot})




# -------------------------
# DASHBOARD
# -------------------------
@login_required
def dashboard(request):
    user = request.user
    profile = user.profile

    if profile.role == 'owner':
        # Owner sees all their businesses and bookings
        businesses = Business.objects.filter(owner=user).prefetch_related('days__slots__appointments')
        business_data = []

        for business in businesses:
            business_info = {
                'business': business,
                'days': []
            }
            for day in business.days.all().order_by('date'):
                day_info = {
                    'day': day,
                    'available_slots': day.slots.filter(is_booked=False).count(),
                    'bookings': Appointment.objects.filter(slot__day=day).select_related('client', 'slot').order_by('slot__start')
                }
                business_info['days'].append(day_info)
            business_data.append(business_info)

        return render(request, 'appointment/dashboard_owner.html', {'business_data': business_data})

    else:
        # Client sees only their appointments and available days
        appointments = Appointment.objects.filter(client=user).select_related('slot__day__business').order_by('slot__day__date', 'slot__start')
        grouped_appointments = {}
        for appt in appointments:
            business = appt.slot.day.business
            if business not in grouped_appointments:
                grouped_appointments[business] = []
            grouped_appointments[business].append(appt)

        # Optionally, show available days per business
        businesses = Business.objects.all().prefetch_related('days__slots')
        business_data = []
        for business in businesses:
            business_info = {
                'business': business,
                'available_days': []
            }
            for day in business.days.all().order_by('date'):
                available_slots = day.slots.filter(is_booked=False)
                if available_slots.exists():
                    business_info['available_days'].append({
                        'day': day,
                        'available_slots_count': available_slots.count()
                    })
            business_data.append(business_info)

        return render(request, 'appointment/dashboard_client.html', {
            'grouped_appointments': grouped_appointments,
            'business_data': business_data
        })


# -------------------------
# BUSINESS DETAIL
# -------------------------
@login_required
def business_detail(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    profile = request.user.profile

    # Owners see all bookings for their business
    if profile.role == 'owner' and business.owner == request.user:
        days_info = []
        for day in business.days.all().order_by('date'):
            bookings = Appointment.objects.filter(slot__day=day).select_related('client', 'slot').order_by('slot__start')
            available_slots = day.slots.filter(is_booked=False).count()
            days_info.append({
                'day': day,
                'available_slots': available_slots,
                'bookings': bookings
            })
        return render(request, 'appointment/business_detail_owner.html', {
            'business': business,
            'days_info': days_info
        })

    # Clients see only available slots
    elif profile.role == 'client':
        days_info = []
        for day in business.days.all().order_by('date'):
            available_slots = day.slots.filter(is_booked=False)
            if available_slots.exists():
                days_info.append({
                    'day': day,
                    'available_slots': available_slots
                })
        return render(request, 'appointment/business_detail_client.html', {
            'business': business,
            'days_info': days_info
        })

    else:
        # Unauthorized access
        return render(request, 'appointment/error.html', {'message': 'You do not have permission to view this business.'})


# -------------------------
# DAY DETAIL
# -------------------------
@login_required
def day_detail(request, day_id):
    day = get_object_or_404(Day, id=day_id)
    profile = request.user.profile

    if profile.role == 'owner' and day.business.owner == request.user:
        # Owner sees all bookings for this day
        bookings = Appointment.objects.filter(slot__day=day).select_related('client', 'slot').order_by('slot__start')
        slots_info = []
        for slot in day.slots.all().order_by('start'):
            slots_info.append({
                'slot': slot,
                'bookings': slot.appointments.all()
            })
        return render(request, 'appointment/day_detail_owner.html', {
            'day': day,
            'slots_info': slots_info
        })

    elif profile.role == 'client':
        # Client sees their booking for this day and available slots
        client_booking = Appointment.objects.filter(client=request.user, slot__day=day).first()
        available_slots = day.slots.filter(is_booked=False)
        return render(request, 'appointment/day_detail_client.html', {
            'day': day,
            'available_slots': available_slots,
            'client_booking': client_booking
        })

    else:
        return render(request, 'appointment/error.html', {'message': 'You do not have permission to view this day.'})

@login_required
def cancel_booking_view(request, slot_id):
    slot = get_object_or_404(TimeSlot, id=slot_id)

    try:
        appointment = Appointment.objects.get(slot=slot)
    except Appointment.DoesNotExist:
        messages.error(request, "No booking exists for this slot.")
        return redirect('calendar:dashboard')

    profile = request.user.profile

    # Client cancels their own booking
    if profile.role == 'client' and appointment.client == request.user:
        appointment.delete()
        slot.is_booked = False
        slot.save()
        messages.success(request, f"Your booking on {slot.day.date} at {slot.start} has been canceled.")
        return redirect('calendar:dashboard')

    # Owner/Staff cancels a client's booking for their business
    elif profile.role in ['owner', 'staff'] and slot.day.business in request.user.owned_businesses.all():
        appointment.delete()
        slot.is_booked = False
        slot.save()
        messages.success(request, f"Booking for {appointment.client.username} on {slot.day.date} at {slot.start} has been canceled by the business.")
        return redirect('calendar:owner_dashboard', business_id=slot.day.business.id)

    # Unauthorized
    else:
        messages.error(request, "You do not have permission to cancel this booking.")
        return redirect('calendar:dashboard')

    

@login_required
def business_list(request):
    """
    Show businesses depending on user role:
    - Owner: only their own businesses
    - Client: all businesses available to book
    """
    profile = request.user.profile

    if profile.role == 'owner':
        # Owners see only their businesses
        businesses = Business.objects.filter(owner=request.user).order_by('name')
    else:
        # Clients see all businesses
        businesses = Business.objects.all().order_by('name')

    return render(request, 'appointment/business_list.html', {
        'businesses': businesses
    })


#uI MANge

@login_required
@owner_required
def owner_dashboard(request, business_id):
    business = get_object_or_404(Business, id=business_id, owner=request.user)

    staff_members = business.staff.all()

    return render(request, "appointment/owner_dashboard.html", {
        "business": business,
        "staff_members": staff_members,
    })

@login_required
@owner_required
def add_staff(request, business_id):
    business = get_object_or_404(Business, id=business_id, owner=request.user)

    if request.method == "POST":
        username = request.POST.get("username")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, "User does not exist.")
            return redirect("calendar:add_staff", business_id=business.id)

        # Assign to business staff
        business.staff.add(user)

        # Assign Django permissions group
        staff_group = Group.objects.get(name="Business Staff")
        user.groups.add(staff_group)

        messages.success(request, f"{user.username} added as staff.")
        return redirect("calendar:owner_dashboard", business_id=business.id)

    return render(request, "appointment/add_staff.html", {
        "business": business,
    })

@login_required
@owner_required
def owner_permissions(request, business_id):
    business = get_object_or_404(Business, id=business_id, owner=request.user)

    group = Group.objects.get(name="Business Staff")
    permissions = group.permissions.all()

    return render(request, "appointment/owner_permissions.html", {
        "business": business,
        "group": group,
        "permissions": permissions
    })


@login_required
def business_detail_staff(request, business_id):
    business = get_object_or_404(Business, id=business_id)

    # Permission: owner or assigned staff only
    if request.user != business.owner and request.user not in business.staff.all():
        messages.error(request, "You do not have access to this business.")
        return redirect("calendar:dashboard")

    days = business.days.order_by("date")

    return render(request, "appointment/business_detail_staff.html", {
        "business": business,
        "days": days
    })

@login_required
@owner_required
def remove_staff(request, business_id, user_id):
    business = get_object_or_404(Business, id=business_id, owner=request.user)

    staff_user = get_object_or_404(User, id=user_id)

    # Prevent removing the owner
    if staff_user == business.owner:
        messages.error(request, "You cannot remove the owner from the business.")
        return redirect("calendar:owner_dashboard", business_id=business.id)

    # Check that the user *is* staff of this business
    if staff_user not in business.staff.all():
        messages.error(request, "This user is not a staff member of your business.")
        return redirect("calendar:owner_dashboard", business_id=business.id)

    if request.method == "POST":
        # Remove from business staff
        business.staff.remove(staff_user)

        # Remove from Django permissions group
        try:
            staff_group = Group.objects.get(name="Business Staff")
            staff_user.groups.remove(staff_group)
        except Group.DoesNotExist:
            pass

        messages.success(request, f"{staff_user.username} has been removed from your staff.")
        return redirect("calendar:owner_dashboard", business_id=business.id)

    return render(request, "appointment/remove_staff_confirm.html", {
        "business": business,
        "staff_user": staff_user,
    })



@login_required
def create_day(request, business_id):
    business = get_object_or_404(Business, id=business_id)

    if request.method == "POST":
        day_date_str = request.POST.get("date")  # assume you have a <input name="date">
        day_date = date.fromisoformat(day_date_str)

        # Check if day already exists
        if Day.objects.filter(business=business, date=day_date).exists():
            messages.error(request, f"A day for {day_date} already exists.")
            return redirect('calendar:business_detail', business_id=business.id)

        # Optional: prevent past dates
        if day_date < date.today():
            messages.error(request, "Cannot create a day in the past.")
            return redirect('calendar:business_detail', business_id=business.id)

        # Create the day
        Day.objects.create(business=business, date=day_date)
        messages.success(request, f"Day {day_date} created successfully.")
        return redirect('calendar:business_detail', business_id=business.id)

    # GET request: show a form
    return render(request, 'appointment/create_day.html', {'business': business})
