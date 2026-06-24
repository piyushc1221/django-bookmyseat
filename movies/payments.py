import base64
import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from urllib import request as urlrequest
from urllib.error import URLError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Booking, PaymentTransaction, Seat
from .reservations import release_expired_reservations


PAYMENT_TIMEOUT_MINUTES = 2


class PaymentError(Exception):
    pass


def ticket_price_paise():
    return int(getattr(settings, "TICKET_PRICE_PAISE", 25000))


def razorpay_key_id():
    return getattr(settings, "RAZORPAY_KEY_ID", "")


def razorpay_key_secret():
    return getattr(settings, "RAZORPAY_KEY_SECRET", "")


def razorpay_webhook_secret():
    return getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")


def create_razorpay_order(amount, currency, receipt, notes):
    if not razorpay_key_id() or not razorpay_key_secret():
        raise PaymentError("Razorpay keys are not configured.")

    payload = json.dumps({
        "amount": amount,
        "currency": currency,
        "receipt": receipt,
        "payment_capture": 1,
        "notes": notes,
    }).encode("utf-8")

    auth_token = base64.b64encode(
        f"{razorpay_key_id()}:{razorpay_key_secret()}".encode("utf-8")
    ).decode("ascii")
    gateway_request = urlrequest.Request(
        "https://api.razorpay.com/v1/orders",
        data=payload,
        headers={
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(gateway_request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise PaymentError("Unable to create payment order. Please try again.") from exc


def start_payment_for_user(user, theatre):
    release_expired_reservations()
    now = timezone.now()

    with transaction.atomic():
        seats = list(
            Seat.objects.select_for_update()
            .filter(
                theatre=theatre,
                reserved_by=user,
                reserved_until__gt=now,
                is_booked=False,
            )
            .order_by("id")
        )

        if not seats:
            raise PaymentError("Reservation expired. Please select seats again.")

        amount = len(seats) * ticket_price_paise()
        seat_id_set = {seat.id for seat in seats}
        pending_payments = PaymentTransaction.objects.select_for_update().filter(
            user=user,
            theatre=theatre,
            status="pending",
            expires_at__gt=now,
        )
        for pending_payment in pending_payments:
            if set(pending_payment.seats.values_list("id", flat=True)) == seat_id_set:
                for seat in seats:
                    seat.reserved_until = pending_payment.expires_at
                    seat.save(update_fields=["reserved_until"])
                return pending_payment

        idempotency_key = f"pay-{uuid.uuid4()}"
        receipt = idempotency_key[:40]
        order = create_razorpay_order(
            amount=amount,
            currency="INR",
            receipt=receipt,
            notes={
                "user_id": str(user.id),
                "theatre_id": str(theatre.id),
                "seat_ids": ",".join(str(seat.id) for seat in seats),
            },
        )

        payment = PaymentTransaction.objects.create(
            user=user,
            theatre=theatre,
            amount=amount,
            currency=order.get("currency", "INR"),
            provider_order_id=order["id"],
            idempotency_key=idempotency_key,
            expires_at=now + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES),
        )
        payment.seats.set(seats)
        for seat in seats:
            seat.reserved_until = payment.expires_at
            seat.save(update_fields=["reserved_until"])
        return payment


def verify_checkout_signature(order_id, payment_id, signature):
    message = f"{order_id}|{payment_id}".encode("utf-8")
    expected_signature = hmac.new(
        razorpay_key_secret().encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature or "")


def verify_webhook_signature(raw_body, signature):
    if not razorpay_webhook_secret():
        return False

    expected_signature = hmac.new(
        razorpay_webhook_secret().encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature or "")


def complete_payment(order_id, payment_id, signature, source="checkout"):
    now = timezone.now()

    with transaction.atomic():
        payment = (
            PaymentTransaction.objects.select_for_update()
            .get(provider_order_id=order_id)
        )

        if payment.status == "paid":
            return payment

        if payment.status != "pending":
            raise PaymentError("Payment is no longer pending.")

        if payment.expires_at <= now:
            expire_payment(payment)
            raise PaymentError("Payment timed out. Please reserve seats again.")

        if source == "checkout" and not verify_checkout_signature(order_id, payment_id, signature):
            payment.status = "failed"
            payment.failure_reason = "Invalid checkout signature."
            payment.save(update_fields=["status", "failure_reason", "updated_at"])
            release_payment_seats(payment)
            raise PaymentError("Payment verification failed.")

        seats = list(
            Seat.objects.select_for_update()
            .filter(
                payments=payment,
                reserved_by=payment.user,
                reserved_until__gt=now,
                is_booked=False,
            )
            .order_by("id")
        )

        if len(seats) != payment.seats.count():
            expire_payment(payment)
            raise PaymentError("Seat reservation expired before payment completion.")

        payment.provider_payment_id = payment_id
        payment.provider_signature = signature
        payment.status = "paid"
        payment.save(update_fields=["provider_payment_id", "provider_signature", "status", "updated_at"])

        for seat in seats:
            try:
                Booking.objects.create(
                    user=payment.user,
                    seat=seat,
                    movie=payment.theatre.movie,
                    theatre=payment.theatre,
                    payment=payment,
                )
            except IntegrityError:
                pass

            seat.is_booked = True
            seat.reserved_by = None
            seat.reserved_at = None
            seat.reserved_until = None
            seat.save(update_fields=["is_booked", "reserved_by", "reserved_at", "reserved_until"])

    return payment


def fail_payment(order_id, reason="Payment failed."):
    with transaction.atomic():
        payment = (
            PaymentTransaction.objects.select_for_update()
            .filter(provider_order_id=order_id)
            .first()
        )
        if not payment or payment.status == "paid":
            return payment

        payment.status = "failed"
        payment.failure_reason = reason
        payment.save(update_fields=["status", "failure_reason", "updated_at"])
        release_payment_seats(payment)
        return payment


def cancel_payment(payment):
    with transaction.atomic():
        payment = PaymentTransaction.objects.select_for_update().get(id=payment.id)
        if payment.status == "pending":
            payment.status = "cancelled"
            payment.failure_reason = "Payment cancelled by user."
            payment.save(update_fields=["status", "failure_reason", "updated_at"])
            release_payment_seats(payment)
    return payment


def expire_payment(payment):
    if payment.status != "pending":
        return payment

    payment.status = "expired"
    payment.failure_reason = "Payment timed out."
    payment.save(update_fields=["status", "failure_reason", "updated_at"])
    release_payment_seats(payment)
    return payment


def release_payment_seats(payment):
    payment.seats.filter(is_booked=False, reserved_by=payment.user).update(
        reserved_by=None,
        reserved_at=None,
        reserved_until=None,
    )


def expire_pending_payments():
    now = timezone.now()
    payments = PaymentTransaction.objects.filter(status="pending", expires_at__lte=now)
    for payment in payments:
        with transaction.atomic():
            locked_payment = PaymentTransaction.objects.select_for_update().get(id=payment.id)
            expire_payment(locked_payment)


def webhook_event_id(payload):
    return payload.get("id")
