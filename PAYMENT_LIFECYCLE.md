# Payment Lifecycle

1. The user selects seats and reserves them for 2 minutes.
2. The user clicks "Proceed to Payment".
3. The server checks the active reservation using row-level locks and creates a Razorpay order on the server.
4. Razorpay Checkout opens in the browser.
5. After payment, the browser posts `razorpay_order_id`, `razorpay_payment_id`, and `razorpay_signature` back to the server.
6. The server verifies the signature using `HMAC_SHA256(order_id|payment_id, RAZORPAY_KEY_SECRET)`.
7. Only after verification succeeds, the server locks the selected seat rows again and creates bookings.
8. Razorpay webhooks are accepted only when `X-Razorpay-Signature` matches the raw request body using `RAZORPAY_WEBHOOK_SECRET`.

## Idempotency

- `PaymentTransaction.provider_order_id` is unique.
- `PaymentTransaction.provider_payment_id` is unique.
- `Booking.seat` is a one-to-one field, so the same seat cannot be booked twice.
- `PaymentWebhookEvent.event_id` is unique, so duplicate webhook deliveries are stored and ignored.
- Duplicate checkout callbacks for an already-paid transaction return safely without creating more bookings.

## Failure, Cancellation, And Timeout

- Failed payments mark the transaction as `failed` and release reserved seats.
- Cancelled payments mark the transaction as `cancelled` and release reserved seats.
- Pending payments expire after 2 minutes and release reserved seats.
- A background scheduler clears expired reservations and pending payments.

## Fraud And Replay Protection

- Bookings are never created from frontend success alone.
- Checkout callbacks must pass Razorpay signature verification.
- Webhooks must pass raw-body signature verification.
- Replayed webhook event IDs are ignored.
- Seat rows are locked with `select_for_update()` inside `transaction.atomic()` before final booking.
