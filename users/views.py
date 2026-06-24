from django.contrib.auth.forms import AuthenticationForm,PasswordChangeForm
from .forms import UserRegisterForm,UserUpdateForm
from django.shortcuts import render,redirect
from django.contrib.auth import login,authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from movies.models import Movie,Booking,Seat,Theatre

def home(request):
    movies=Movie.objects.all()
    return render(request,'home.html',{'movies':movies})

@never_cache
@csrf_protect
@ensure_csrf_cookie
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username,password=password)
            login(request,user)
            return redirect('profile')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form' : form})

@never_cache
@csrf_protect
@ensure_csrf_cookie
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request,data = request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request,user)
            return redirect('/')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form' : form})

@login_required
def profile(request):
    bookings=Booking.objects.filter(user=request.user)
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST,instance = request.POST)
        if u_form.is_valid():
            u_form.save()
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
    return render(request, 'users/profile.html', {'u_form' : u_form,'bookings':bookings})
 
@login_required
def reset_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user,instance = request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = PasswordChangeForm(instance=request.user)
    return render(request, 'users/reset_password.html', {'form' : form})
