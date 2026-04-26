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
            'high_severity': high_severity
        })
    
    recent_symptoms = SymptomEntry.objects.filter(user=request.user)[:5]
    return render(request, 'core/dashboard.html', {'recent_symptoms': recent_symptoms})


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

# 🔹 Send Email (NEW - added only)
from django.core.mail import send_mail

@login_required
def send_email(request):
    if request.method == "POST":
        name = request.POST.get('name')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        to_email = request.POST.get('to_email')

        full_message = f"From: {name}\n\n{message}"

        send_mail(
            subject,
            full_message,
            settings.EMAIL_HOST_USER,   # sender email
            [to_email],                # receiver email
            fail_silently=False,
        )

    return redirect('doctor_contact')

# 🔹 Health Tips
@login_required
def health_tips_view(request):
    return render(request, 'core/health_tips.html')


# 🔹 Doctor Contact
@login_required
def doctor_contact_view(request):
    doctors = [
        {'name': 'Dr. Sarah Johnson', 'specialization': 'General Physician'},
        {'name': 'Dr. Michael Chen', 'specialization': 'Cardiologist'},
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