from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages

# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

User = get_user_model()


# Create your views here.
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username") or None
        password = request.POST.get("password") or None
        # eval("print('hello')")
        if all([username, password]):
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("/")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Please provide both username and password.")
    return render(request, "auth/login.html", {})


def register_view(request):
    if request.method == "POST":
        # print(request.POST)
        username = request.POST.get("username") or None
        email = request.POST.get("email") or None
        password = request.POST.get("password") or None
        # Django Forms
        # username_exists = User.objects.filter(username__iexact=username).exists()
        # email_exists = User.objects.filter(email__iexact=email).exists()
        if all([username, email, password]):
            # Check if username already exists
            if User.objects.filter(username__iexact=username).exists():
                messages.error(
                    request, "Username already exists. Please choose a different one."
                )
            # Check if email already exists
            elif User.objects.filter(email__iexact=email).exists():
                messages.error(
                    request, "Email already registered. Please use a different email."
                )
            else:
                try:
                    User.objects.create_user(username, email=email, password=password)
                    messages.success(
                        request, "Account created successfully! Please log in."
                    )
                    return redirect("/login/")
                except Exception as e:
                    messages.error(
                        request,
                        "An error occurred while creating your account. Please try again.",
                    )
        else:
            messages.error(request, "Please fill in all fields.")
    return render(request, "auth/register.html", {})
