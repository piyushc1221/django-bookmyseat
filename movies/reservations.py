from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Seat


RESERVATION_MINUTES = 2


def reservation_deadline():
    return timezone.now() + timedelta(minutes=RESERVATION_MINUTES)


def release_expired_reservations():
    now = timezone.now()
    return Seat.objects.filter(
        is_booked=False,
        reserved_until__isnull=False,
        reserved_until__lte=now,
    ).update(
        reserved_by=None,
        reserved_at=None,
        reserved_until=None,
    )


def release_user_reservations(user, theatre, keep_seat_ids=None):
    keep_seat_ids = keep_seat_ids or []
    seats = Seat.objects.filter(
        theatre=theatre,
        reserved_by=user,
        is_booked=False,
    )
    if keep_seat_ids:
        seats = seats.exclude(id__in=keep_seat_ids)

    return seats.update(
        reserved_by=None,
        reserved_at=None,
        reserved_until=None,
    )


def reserve_seats_for_user(user, theatre, seat_ids):
    now = timezone.now()
    deadline = reservation_deadline()
    try:
        seat_ids = [int(seat_id) for seat_id in seat_ids]
    except ValueError:
        return False, "Invalid seat selection."

    with transaction.atomic():
        release_expired_reservations()

        seats = list(
            Seat.objects.select_for_update()
            .filter(theatre=theatre, id__in=seat_ids)
            .order_by("id")
        )

        if len(seats) != len(set(seat_ids)):
            return False, "Invalid seat selection."

        unavailable = []
        for seat in seats:
            reserved_by_other_user = (
                seat.reserved_until
                and seat.reserved_until > now
                and seat.reserved_by_id != user.id
            )
            if seat.is_booked or reserved_by_other_user:
                unavailable.append(seat.seat_no)

        if unavailable:
            return False, f"Seat(s) already unavailable: {', '.join(unavailable)}"

        release_user_reservations(user, theatre, keep_seat_ids=seat_ids)

        for seat in seats:
            seat.reserved_by = user
            seat.reserved_at = now
            seat.reserved_until = deadline
            seat.save(update_fields=["reserved_by", "reserved_at", "reserved_until"])

    return True, f"Seat(s) reserved for {RESERVATION_MINUTES} minutes."
