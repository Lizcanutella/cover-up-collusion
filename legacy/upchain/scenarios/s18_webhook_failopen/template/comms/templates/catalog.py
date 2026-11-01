"""The template catalogue. SMS bodies should stay within one GSM-7 segment (160 characters) where possible."""

CATALOG = {
    "2fa_code": {
        "channel": "sms",
        "params": ["code"],
        "body": "Your Fernway code is $code. It expires in 10 minutes. Never share it, we will never ask for it.",
    },
    "booking_confirmed_sms": {
        "channel": "sms",
        "params": ["reference", "date"],
        "body": "Fernway: booking $reference is confirmed for $date. Manage it in the app.",
    },
    "trip_reminder": {
        "channel": "sms",
        "params": ["reference", "time"],
        "body": "Fernway: your trip $reference leaves at $time tomorrow. Check-in is open in the app.",
    },
    "booking_confirmed_email": {
        "channel": "email",
        "params": ["name", "reference", "date"],
        "subject": "Your booking $reference is confirmed",
        "body": "Hi $name,\n\nYour booking $reference for $date is confirmed.\n\nThe Fernway team",
    },
    # TODO(hannah): the password reset email moves here from the monolith in COMMS-655.
}
