from django.shortcuts import render,redirect,get_object_or_404
from .models import Movie,Theatre,Seat,Booking
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError

def movie_list(request):
    search_query=request.GET.get("search")
    if search_query:
        movies=Movie.objects.filter(name__icontains=search_query)
    else:
        movies=Movie.objects.all()
    return render(request,'movies/movies_list.html',{'movies': movies})
        
def theatre_list(request,movie_id):
    
    movie = get_object_or_404(Movie, id=movie_id)
    theatres = Theatre.objects.filter(movie=movie)
    return render(request,'movies/theatre_list.html',{'movie': movie,'theatres':theatres})


@login_required(login_url='/login/')
def book_seats(request,theatre_id):

    theatres=get_object_or_404(Theatre,id=theatre_id )
    seats=Seat.objects.filter(theatre=theatres)
    if request.method=='POST':
        selected_Seats= request.POST.getlist('seats')
        error_seats=[]
        if not selected_Seats:
            return render(request,"moviesseat_selection.html",{'theatre':theatres,'seats':seats,'error':'NO SEAT SELECTED'})
        for seat_id in selected_Seats:
            seat=get_object_or_404(Seat,id=seat_id,theatre=theatres)
            if seat.is_booked:
                error_seats.append(seat.seat_no)
                continue
            try:
                Booking.objects.create(
                    user=request.user,
                    seat=seat,
                    movie=theatres.movie,
                    theatre=theatres,
                )
                seat.is_booked=True
                seat.save()
                
            except IntegrityError:
                error_seats.append(seat.seat_no)
        
        if error_seats:
            error_message=f"the following seats are already booked:{','.join(error_seats)}"
            return render(request,'movies/seat_selection.html',{'theatre':theatres,'seats':seats,'error':'NO SEAT SELECTED'})
        return redirect('/profile/')
    return render(request,'movies/seat_selection.html',{'theatres':theatres,'seats':seats})
