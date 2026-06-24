import json

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from .models import Movie,Theatre,Seat,Booking,PaymentTransaction,PaymentWebhookEvent
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .reservations import release_expired_reservations, reserve_seats_for_user
from .payments import (
    PaymentError,
    cancel_payment,
    complete_payment,
    fail_payment,
    razorpay_key_id,
    start_payment_for_user,
    verify_webhook_signature,
    webhook_event_id,
)

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

    theatre=get_object_or_404(Theatre,id=theatre_id )
    release_expired_reservations()

    if request.method=='POST':
        selected_Seats= request.POST.getlist('seats')
        if not selected_Seats:
            seats, has_user_reservations = get_seat_statuses(theatre, request.user)
            return render(request,'movies/seat_selection.html',{'theatre':theatre,'seats':seats,'error':'NO SEAT SELECTED','has_user_reservations':has_user_reservations})

        success, message = reserve_seats_for_user(request.user, theatre, selected_Seats)
        if not success:
            seats, has_user_reservations = get_seat_statuses(theatre, request.user)
            return render(request,'movies/seat_selection.html',{'theatre':theatre,'seats':seats,'error':message,'has_user_reservations':has_user_reservations})

        return redirect('book_seats', theatre_id=theatre.id)

    seats, has_user_reservations = get_seat_statuses(theatre, request.user)
    return render(request,'movies/seat_selection.html',{'theatre':theatre,'seats':seats,'has_user_reservations':has_user_reservations})


@login_required(login_url='/login/')
def confirm_booking(request,theatre_id):
    theatre=get_object_or_404(Theatre,id=theatre_id)
    if request.method != 'POST':
        return redirect('book_seats', theatre_id=theatre.id)

    try:
        payment = start_payment_for_user(request.user, theatre)
    except PaymentError as exc:
        seats, has_user_reservations = get_seat_statuses(theatre, request.user)
        return render(request,'movies/seat_selection.html',{'theatre':theatre,'seats':seats,'error':str(exc),'has_user_reservations':has_user_reservations})

    return redirect('payment_checkout', payment_id=payment.id)


@login_required(login_url='/login/')
def payment_checkout(request,payment_id):
    payment=get_object_or_404(PaymentTransaction,id=payment_id,user=request.user)
    if payment.status == 'paid':
        return redirect('/profile/')

    if payment.status != 'pending':
        seats, has_user_reservations = get_seat_statuses(payment.theatre, request.user)
        return render(request,'movies/seat_selection.html',{'theatre':payment.theatre,'seats':seats,'error':'Payment is no longer active. Please select seats again.','has_user_reservations':has_user_reservations})

    return render(request,'movies/payment_checkout.html',{
        'payment':payment,
        'amount_display':payment.amount / 100,
        'razorpay_key_id':razorpay_key_id(),
    })


@login_required(login_url='/login/')
def payment_callback(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request.')

    order_id = request.POST.get('razorpay_order_id')
    payment_id = request.POST.get('razorpay_payment_id')
    signature = request.POST.get('razorpay_signature')

    if not order_id or not payment_id or not signature:
        return HttpResponseBadRequest('Missing payment details.')

    try:
        existing_payment = PaymentTransaction.objects.get(provider_order_id=order_id)
        if existing_payment.user_id != request.user.id:
            return HttpResponseBadRequest('Invalid payment user.')
        payment = complete_payment(order_id, payment_id, signature, source='checkout')
    except (PaymentError, PaymentTransaction.DoesNotExist) as exc:
        return render(request,'movies/payment_failed.html',{'error':str(exc)})

    return redirect('/profile/')


@login_required(login_url='/login/')
def payment_cancel(request,payment_id):
    payment=get_object_or_404(PaymentTransaction,id=payment_id,user=request.user)
    if request.method != 'POST':
        return redirect('payment_checkout', payment_id=payment.id)

    cancel_payment(payment)
    seats, has_user_reservations = get_seat_statuses(payment.theatre, request.user)
    return render(request,'movies/seat_selection.html',{'theatre':payment.theatre,'seats':seats,'error':'Payment cancelled. Please reserve seats again.','has_user_reservations':has_user_reservations})


@csrf_exempt
def razorpay_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request.')

    raw_body = request.body
    signature = request.headers.get('X-Razorpay-Signature', '')
    if not verify_webhook_signature(raw_body, signature):
        return HttpResponseBadRequest('Invalid webhook signature.')

    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')

    event_id = webhook_event_id(payload)
    if not event_id:
        return HttpResponseBadRequest('Missing webhook event id.')

    event_type = payload.get('event', '')
    payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
    order_id = payment_entity.get('order_id')
    provider_payment_id = payment_entity.get('id')
    paid_amount = payment_entity.get('amount')

    payment = PaymentTransaction.objects.filter(provider_order_id=order_id).first()

    try:
        PaymentWebhookEvent.objects.create(
            event_id=event_id,
            event_type=event_type,
            payment=payment,
        )
    except IntegrityError:
        return JsonResponse({'status':'duplicate'})

    if not payment:
        return JsonResponse({'status':'ignored'})

    try:
        amount_matches = paid_amount is None or int(paid_amount) == payment.amount
    except (TypeError, ValueError):
        amount_matches = False

    if not amount_matches:
        fail_payment(order_id, 'Webhook amount did not match expected ticket amount.')
        return HttpResponseBadRequest('Invalid payment amount.')

    if event_type == 'payment.captured':
        try:
            complete_payment(order_id, provider_payment_id, '', source='webhook')
        except PaymentError:
            pass
    elif event_type == 'payment.failed':
        fail_payment(order_id, payment_entity.get('error_description') or 'Payment failed.')

    return JsonResponse({'status':'ok'})


@login_required(login_url='/login/')
def seat_status(request,theatre_id):
    theatre=get_object_or_404(Theatre,id=theatre_id)
    release_expired_reservations()
    seats, has_user_reservations = get_seat_statuses(theatre, request.user)

    return JsonResponse({
        'has_user_reservations': has_user_reservations,
        'seats': [
            {
                'id': seat.id,
                'seat_no': seat.seat_no,
                'status': seat.status,
                'seconds_left': seat.seconds_left,
            }
            for seat in seats
        ],
    })


def get_seat_statuses(theatre, user):
    now = timezone.now()
    seats = list(Seat.objects.filter(theatre=theatre).order_by('seat_no'))
    has_user_reservations = False

    for seat in seats:
        seat.seconds_left = 0
        if seat.is_booked:
            seat.status = 'booked'
        elif seat.reserved_until and seat.reserved_until > now:
            seat.seconds_left = int((seat.reserved_until - now).total_seconds())
            if seat.reserved_by_id == user.id:
                seat.status = 'reserved_by_you'
                has_user_reservations = True
            else:
                seat.status = 'reserved'
        else:
            seat.status = 'available'

    return seats, has_user_reservations
