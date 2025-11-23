from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'calendar'

urlpatterns = [
    # -------------------------
    # AUTHENTICATION
    # -------------------------
    path('signup/', views.signup, name='signup'),  # Any user
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='calendar:login'), name='logout'),

    # -------------------------
    # DASHBOARD
    # -------------------------
    path('dashboard/', views.dashboard, name='dashboard'),

    # -------------------------
    # BUSINESS
    # -------------------------
    path('business/create/', views.create_business, name='create_business'),  # Owner only
    path('business/<int:business_id>/', views.business_detail, name='business_detail'),  # Owner / Client
    path('businesses/', views.business_list, name='business_list'),  # Client / Owner

    # -------------------------
    # DAY MANAGEMENT
    # -------------------------
    path('business/<int:business_id>/day/create/', views.create_day, name='create_day'),  # Owner only
    path('day/<int:day_id>/', views.day_detail, name='day_detail'),  # Owner / Client
    path('business/<int:business_id>/day/create/', views.create_day, name='create_day'),

    # -------------------------
    # SLOT GENERATION
    # -------------------------
    path('day/<int:day_id>/generate_slots/', views.generate_slots, name='generate_slots'),  # Owner / Staff

    # -------------------------
    # APPOINTMENT BOOKING
    # -------------------------
    path('slot/<int:slot_id>/book/', views.book_slot, name='book_slot'),  # Client only
    path('slot/<int:slot_id>/cancel/', views.cancel_booking_view, name='cancel_booking'),  # Client only

    # -------------------------
    # OWNER DASHBOARD / STAFF MANAGEMENT
    # -------------------------
    path('business/<int:business_id>/owner-dashboard/', views.owner_dashboard, name='owner_dashboard'),  # Owner
    path('business/<int:business_id>/add-staff/', views.add_staff, name='add_staff'),  # Owner
    path('business/<int:business_id>/remove-staff/<int:user_id>/', views.remove_staff, name='remove_staff'),  # Owner
    path('business/<int:business_id>/permissions/', views.owner_permissions, name='owner_permissions'),  # Owner

    # -------------------------
    # STAFF VIEW
    # -------------------------
    path('business/<int:business_id>/staff/', views.business_detail_staff, name='business_detail_staff'),  # Owner / Staff
]
