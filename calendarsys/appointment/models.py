from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import models
from datetime import date

class UserProfile(models.Model):
    USER_ROLES = (
        ('owner', 'Business Owner'),
        ('client', 'Client'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=USER_ROLES)
    
    # Only for clients: which business they are associated with
    business = models.ForeignKey(
        'Business', null=True, blank=True, on_delete=models.SET_NULL, related_name='clients'
    )

    def __str__(self):
        if self.role == 'client' and self.business:
            return f"{self.user.username} ({self.role}) - {self.business.name}"
        return f"{self.user.username} ({self.role})"

class BusinessStaff(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    business = models.ForeignKey("Business", on_delete=models.CASCADE)
    
    is_active = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'business')

class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_businesses")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    staff = models.ManyToManyField(User, through=BusinessStaff, related_name="business_staff")


    def __str__(self):
        return self.name
from django.db import models
from django.core.exceptions import ValidationError
from datetime import date

class Day(models.Model):
    date = models.DateField()
    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name="days")

    class Meta:
        unique_together = ('date', 'business')
        ordering = ['date']

    def __str__(self):
        return f"{self.business.name} - {self.date}"

    def clean(self):
        """Prevent creating a day in the past."""
        super().clean()
        if self.date and self.date < date.today():
            raise ValidationError("You cannot create a day in the past.")



from django.core.exceptions import ValidationError
from django.utils.timezone import now

class TimeSlot(models.Model):
    day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name="slots")
    start = models.TimeField()
    end = models.TimeField()
    is_booked = models.BooleanField(default=False)

    class Meta:
        ordering = ['start']

    def __str__(self):
        return f"{self.day} {self.start}-{self.end}"

    def clean(self):
        # Ensure start is before end
        if self.start >= self.end:
            raise ValidationError("Start time must be before end time")
        
        # Prevent overlapping slots on the same day
        overlapping = TimeSlot.objects.filter(
            day=self.day,
            start__lt=self.end,
            end__gt=self.start
        )
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError("This time slot overlaps with an existing slot.")

        # Optional: prevent booking past slots
        if self.day.date < now().date():
            raise ValidationError("Cannot create a slot for a past day.")

    def save(self, *args, **kwargs):
        # Ensure clean is called
        self.full_clean()

        # If the slot is already booked and someone tries to save it as booked again
        if self.pk and self.is_booked:
            orig = TimeSlot.objects.get(pk=self.pk)
            if orig.is_booked and self.is_booked:
                raise ValidationError("This slot is already booked")

        super().save(*args, **kwargs)



class Appointment(models.Model):
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="appointments")
    slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name="appointments")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Only clients can book appointments
        if self.client.profile.role != 'client':
            raise ValidationError("Only clients can book appointments.")

        # Concurrency-safe booking
        with transaction.atomic():
            self.slot.refresh_from_db()
            if self.slot.is_booked:
                raise ValidationError("This slot is already booked")
            self.slot.is_booked = True
            self.slot.save()
            super().save(*args, **kwargs)
            



