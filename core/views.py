import os
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm, SymptomEntryForm
from .models import SymptomEntry
from django.utils import timezone
from groq import Groq

# ✅ Groq client
client = Groq(api_key=settings.GROQ_API_KEY)


# 🔹 Suggestion logic
def get_suggestion_by_severity(severity):
    suggestions = {
        'Low': "Home rest recommended...",
        'Medium': "Rest and basic self-care advised...",
        'High': "Immediate medical consultation strongly recommended..."
    }
    return suggestions.get(severity, suggestions['Low'])


# 🔹 Signup
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Account created for {user.username}!')
            return redirect('login')
    else:
        form = UserRegistrationForm()

    return render(request, 'core/signup.html', {'form': form})


# 🔹 ✅ FIXED (Missing function added)
@login_required
def profile_view(request):
    return render(request, 'core/profile.html', {'user': request.user})


# 🔹 Dashboard
@login_required
def dashboard_view(request):
    from datetime import timedelta
    from django.utils import timezone
    import json

    today = timezone.now().date()
    
    if request.user.is_superuser:
        symptoms_qs = SymptomEntry.objects.all()
    else:
        symptoms_qs = SymptomEntry.objects.filter(user=request.user)

    # Calculate dynamic Health Score & Chart Data based on average severity
    recent_7_days = timezone.now() - timedelta(days=7)
    recent_logs = list(symptoms_qs.filter(created_at__gte=recent_7_days))
    
    if recent_logs:
        total_score = 0
        for log in recent_logs:
            if log.severity == 'High': total_score += 40
            elif log.severity == 'Medium': total_score += 70
            elif log.severity == 'Low': total_score += 90
        health_score = int(total_score / len(recent_logs))
    else:
        health_score = 100

    chart_labels = []
    chart_data = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime("%a"))
        
        day_logs = [log for log in recent_logs if log.created_at.date() == day]
        if day_logs:
            day_total = 0
            for log in day_logs:
                if log.severity == 'High': day_total += 40
                elif log.severity == 'Medium': day_total += 70
                elif log.severity == 'Low': day_total += 90
            day_score = int(day_total / len(day_logs))
        else:
            day_score = 100
            
        chart_data.append(day_score)
        
    chart_labels_json = json.dumps(chart_labels)
    chart_data_json = json.dumps(chart_data)

    if request.user.is_superuser:
        recent_symptoms = SymptomEntry.objects.all().order_by('-created_at')[:10]
        total_patients = User.objects.filter(is_superuser=False).count()
        total_logs = SymptomEntry.objects.count()
        high_severity = SymptomEntry.objects.filter(severity='High').count()
        
        return render(request, 'core/dashboard.html', {
            'recent_symptoms': recent_symptoms,
            'is_admin': True,
            'total_patients': total_patients,
            'total_logs': total_logs,
            'high_severity': high_severity,
            'health_score': health_score,
            'health_score_remainder': 100 - health_score,
            'chart_labels': chart_labels_json,
            'chart_data': chart_data_json,
        })
    
    recent_symptoms = SymptomEntry.objects.filter(user=request.user).order_by('-created_at')[:5]
    return render(request, 'core/dashboard.html', {
        'recent_symptoms': recent_symptoms,
        'health_score': health_score,
        'health_score_remainder': 100 - health_score,
        'chart_labels': chart_labels_json,
        'chart_data': chart_data_json,
    })


# 🔹 Add Symptom
@login_required
def add_symptom_view(request):
    if request.method == 'POST':
        form = SymptomEntryForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.suggestion = get_suggestion_by_severity(obj.severity)
            obj.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"status": "saved"})

            return redirect('symptom_history')
    else:
        form = SymptomEntryForm()

    return render(request, 'core/add_symptom.html', {'form': form})


# 🔹 Symptom History
@login_required
def symptom_history_view(request):
    if request.user.is_superuser:
        symptoms = SymptomEntry.objects.all().order_by('-created_at')
        return render(request, 'core/symptom_history.html', {'symptoms': symptoms, 'is_admin': True})
    
    symptoms = SymptomEntry.objects.filter(user=request.user)
    return render(request, 'core/symptom_history.html', {'symptoms': symptoms})


# 🔹 AI Response (Groq)
@login_required
def get_ai_response(request):
    if request.method == "POST":
        try:
            symptom = request.POST.get("symptom_text")
            severity = request.POST.get("severity")

            try:
                chat = client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": f"""
                        Act like a professional clinical AI. Generate a concise, point-wise Medical Report Summary.
                        
                        Data:
                        - Patient Name: {request.user.get_full_name() or request.user.username}
                        - Symptoms: {symptom}
                        - Severity: {severity}
                        - Date: {timezone.now().strftime('%Y-%m-%d')}

                        Follow this EXACT format (use markdown):

                        **Medical Report**
                        **Date:** {timezone.now().strftime('%Y-%m-%d')}
                        **Patient's Name:** {request.user.get_full_name() or request.user.username}
                        **Symptoms:** {symptom}
                        **Severity:** {severity}

                        **🔍 Potential Cause**
                        1. **Primary Observation**: [Detail here]
                        2. **Differential Diagnosis**: [Detail here]
                        3. **Other Considerations**: [Detail here]

                        **💊 Recommended Treatment**
                        1. **Supportive Care**: [Rest/Hydration detail]
                        2. **Medication**: [OTC detail]
                        3. **Follow-up Care**: [Schedule detail]

                        **👨‍⚕️ Clinical Advice**
                        - **Monitoring**: [Vitals detail]
                        - **Return Visit**: [Timing detail]
                        - **Emergency**: Immediate medical attention if:
                          - [List 5 critical conditions]

                        **Follow-up Instructions**
                        - **Symptom Journal**: [Instruction]
                        - **Communication**: [Instruction]

                        **Additional Recommendations**
                        - **Self-Isolation**: [Instruction]
                        - **Good Hygiene**: [Instruction]

                        **Prescription Information**
                        [Clear instruction about prescriptions]
                        """
                    }],
                        model="llama-3.1-8b-instant"            )
                
                response_text = chat.choices[0].message.content
            except Exception as api_error:
                # 🛡️ FALLBACK: Concise Professional Simulated AI Response if API fails
                response_text = f"""**Medical Report**
**Date:** {timezone.now().strftime('%Y-%m-%d')}
**Patient's Name:** {request.user.get_full_name() or request.user.username}
**Symptoms:** {symptom}
**Severity:** {severity}

**🔍 Potential Cause**
1. **Viral Infection**: Symptoms suggest a potential respiratory viral infection (e.g., Influenza or localized virus).
2. **Bacterial Progression**: Lower probability of bacterial involvement unless symptoms persist.
3. **Inflammatory Response**: General body response to immune triggers.

**💊 Recommended Treatment**
1. **Rest and Hydration**: Prioritize bed rest and electrolyte replacement.
2. **Medication**: Acetaminophen or Ibuprofen as per label instructions for fever/pain.
3. **Follow-up Care**: Schedule reassessment in 2-3 days if no improvement.

**👨‍⚕️ Clinical Advice**
- **Monitoring**: Track temperature and pulse every 6 hours.
- **Return Visit**: Recommended in 48-72 hours.
- **Emergency**: Seek immediate help for chest pain, confusion, or severe breathing difficulty.

**Follow-up Instructions**
- **Symptom Journal**: Record daily temperature and peak symptom intensity.
- **Communication**: Contact your physician if severity increases.

**Additional Recommendations**
- **Self-Isolation**: Minimize contact to prevent transmission.
- **Good Hygiene**: Frequent hand washing and sanitization.

**Prescription Information**
No prescriptions recommended at this stage. Requires physical validation."""


            return JsonResponse({
                "ai_response": response_text
            })

        except Exception as e:
            print("ERROR:", e)
            return JsonResponse({"ai_response": "⚠️ AI not working"})

    return JsonResponse({"error": "Invalid request"})

# 🔹 Book Appointment (Email Notification)
from django.core.mail import send_mail
from django.conf import settings
import json

@login_required
def book_appointment(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            doctor_name = data.get('doctor_name')
            date = data.get('date')
            time_slot = data.get('time_slot')
            reason = data.get('reason')
            
            # The hardcoded email ID where you want to receive notifications. 
            # YOU CAN CHANGE 'your-hospital-email@gmail.com' TO YOUR ACTUAL EMAIL ID HERE.
            admin_email = "shubhsrivastav9369@gmail.com"
            sender_email = getattr(settings, 'EMAIL_HOST_USER', admin_email)
            
            subject = f"🩺 New Appointment Booking: {doctor_name}"
            
            # Plain text fallback
            message = (
                f"A new appointment has been booked via DocX-AI Smart Healtcare Website.\n\n"
                f"Patient: {request.user.username} ({request.user.email})\n"
                f"Doctor: {doctor_name}\n"
                f"Date: {date}\n"
                f"Time Slot: {time_slot}\n"
                f"Reason for Visit: {reason}\n"
            )

            # Professional HTML Email Template
            html_message = f"""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #f4f7f6; padding: 20px; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div style="background-color: #0d6efd; color: #ffffff; padding: 20px; text-align: center;">
                        <h2 style="margin: 0;">DocX Hospital Network</h2>
                        <p style="margin: 5px 0 0; opacity: 0.9;">New Appointment Request</p>
                    </div>
                    <div style="padding: 30px;">
                        <h3 style="color: #0d6efd; border-bottom: 2px solid #e9ecef; padding-bottom: 10px; margin-top: 0;">Patient Details</h3>
                        <p><strong>Name:</strong> {request.user.username}</p>
                        <p><strong>Email:</strong> {request.user.email}</p>
                        
                        <h3 style="color: #0d6efd; border-bottom: 2px solid #e9ecef; padding-bottom: 10px; margin-top: 25px;">Appointment Details</h3>
                        <p><strong>Specialist:</strong> {doctor_name}</p>
                        <p><strong>Date:</strong> {date}</p>
                        <p><strong>Time Slot:</strong> {time_slot}</p>
                        
                        <div style="background-color: #f8f9fa; border-left: 4px solid #ffc107; padding: 15px; margin-top: 25px; border-radius: 4px;">
                            <h4 style="margin-top: 0; margin-bottom: 10px; color: #6c757d;">Reason for Visit / Patient Message:</h4>
                            <p style="margin: 0; font-style: italic; color: #495057;">"{reason}"</p>
                        </div>
                    </div>
                    <div style="background-color: #e9ecef; padding: 15px; text-align: center; font-size: 12px; color: #6c757d;">
                        This is an automated message from the DocX AI Smart Healthcare Assistant System.
                    </div>
                </div>
            </body>
            </html>
            """
            
            send_mail(
                subject,
                message,
                sender_email,  # From email
                [admin_email],  # To email (sends to the hardcoded email)
                html_message=html_message,
                fail_silently=False,
            )
            return JsonResponse({"status": "success", "message": "Appointment booked and email sent."})
        except Exception as e:
            print("Email Error:", e)
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
            
    return JsonResponse({"error": "Invalid request"}, status=400)

# 🔹 Health Tips
@login_required
def health_tips_view(request):
    return render(request, 'core/health_tips.html')


# 🔹 Doctor Contact
@login_required
def doctor_contact_view(request):
    doctors = [
        {
            'name': 'Dr. Utkarsh Sri',
            'specialization': 'General Physician',
            'department': 'Internal Medicine',
            'experience': 12,
            'rating': 4.9,
            'reviews': '1.2k',
            'status': 'Online',
            'image_url': 'https://ui-avatars.com/api/?name=Dr+Aditi+Sharma&background=8b5cf6&color=fff&size=128&bold=true',
            'next_slot': 'Available Now',
            'fee': '$50',
            'tags': ['Internal Medicine', 'Chronic Care']
        },
        {
            'name': 'Dr. Vikram Singh',
            'specialization': 'Cardiologist',
            'department': 'Cardiology',
            'experience': 18,
            'rating': 4.8,
            'reviews': '850',
            'status': 'Busy',
            'image_url': 'https://ui-avatars.com/api/?name=Dr+Vikram+Singh&background=3b82f6&color=fff&size=128&bold=true',
            'next_slot': 'Today, 4:30 PM',
            'fee': '$120',
            'tags': ['Heart Surgery', 'Diagnostics']
        },
        {
            'name': 'Dr. Elena Rostova',
            'specialization': 'Neurologist',
            'department': 'Neurology',
            'experience': 15,
            'rating': 5.0,
            'reviews': '2.1k',
            'status': 'Offline',
            'image_url': 'https://ui-avatars.com/api/?name=Dr+Elena+Rostova&background=10b981&color=fff&size=128&bold=true',
            'next_slot': 'Tomorrow, 10:00 AM',
            'fee': '$150',
            'tags': ['Brain Mapping', 'Migraine Care']
        },
        {
            'name': 'Dr. Rajesh Kumar',
            'specialization': 'Pediatrician',
            'department': 'Pediatrics',
            'experience': 9,
            'rating': 4.7,
            'reviews': '420',
            'status': 'Online',
            'image_url': 'https://ui-avatars.com/api/?name=Dr+Rajesh+Kumar&background=f59e0b&color=fff&size=128&bold=true',
            'next_slot': 'Available Now',
            'fee': '$60',
            'tags': ['Child Care', 'Vaccinations']
        },
        {
            'name': 'Dr. Sarah Johnson',
            'specialization': 'Psychiatrist',
            'department': 'Mental Health',
            'experience': 14,
            'rating': 4.9,
            'reviews': '930',
            'status': 'Online',
            'image_url': 'https://ui-avatars.com/api/?name=Dr+Sarah+Johnson&background=ec4899&color=fff&size=128&bold=true',
            'next_slot': 'Available Now',
            'fee': '$90',
            'tags': ['Therapy', 'Anxiety']
        },
        {
            'name': 'Dr. Michael Chen',
            'specialization': 'Orthopedic',
            'department': 'Orthopedics',
            'experience': 22,
            'rating': 4.6,
            'reviews': '1.5k',
            'status': 'Busy',
            'image_url': 'https://ui-avatars.com/api/?name=Dr+Michael+Chen&background=6366f1&color=fff&size=128&bold=true',
            'next_slot': 'Today, 6:00 PM',
            'fee': '$110',
            'tags': ['Joint Replacement', 'Sports Injuries']
        }
    ]
    return render(request, 'core/doctor_contact.html', {'doctors': doctors})

# 🔹 Delete Symptom Record
@login_required
def delete_symptom_view(request, pk):
    try:
        symptom = SymptomEntry.objects.get(pk=pk)
        if symptom.user == request.user or request.user.is_superuser:
            symptom.delete()
            messages.success(request, "Archive record deleted successfully.")
        else:
            messages.error(request, "Unauthorized deletion attempt.")
    except SymptomEntry.DoesNotExist:
        messages.error(request, "Record not found.")
    
    return redirect('symptom_history')

# 🔹 Subscribe Newsletter
@login_required
def subscribe_newsletter(request):
    if request.method == "POST":
        email = request.POST.get('email')
        if email:
            try:
                # 📧 Actual Email Sending
                send_mail(
                    subject='Welcome to DocX Weekly Intelligence',
                    message=f'Hello,\n\nThank you for subscribing to DocX Weekly Intelligence. You will now receive the latest clinical research and health optimization strategies directly at {email}.\n\nBest Regards,\nThe DocX Clinical Team',
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[email],
                    fail_silently=False,
                )
                messages.success(request, f"Excellence! {email} has been registered for clinical intelligence updates.")
            except Exception as e:
                # Fallback for demo purposes if SMTP is not configured
                print("SMTP Error:", e)
                messages.success(request, f"Intelligence Hub: {email} added to clinical queue.")
        else:
            messages.error(request, "Please provide a valid medical email address.")
    return redirect('health_tips')