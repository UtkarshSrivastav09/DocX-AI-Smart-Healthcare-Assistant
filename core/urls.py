from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication URLs
    path('signup/', views.signup_view, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    # path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Symptom management
    path('add-symptom/', views.add_symptom_view, name='add_symptom'),
    path('get-ai-response/', views.get_ai_response, name='get_ai_response'),  # ✅ ADDED
    
    path('symptom-history/', views.symptom_history_view, name='symptom_history'),
    path('delete-symptom/<int:pk>/', views.delete_symptom_view, name='delete_symptom'),
    
    # Health tips
    path('health-tips/', views.health_tips_view, name='health_tips'),
    path('subscribe-newsletter/', views.subscribe_newsletter, name='subscribe_newsletter'),

    
    # Doctor contact
    path('doctor-contact/', views.doctor_contact_view, name='doctor_contact'),
    path('book-appointment/', views.book_appointment, name='book_appointment'),
    
    # Redirect root to dashboard (if logged in) or login
    path('', views.dashboard_view, name='home'),
]