from twilio.rest import Client
from app.config import TWILIO_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM


def send_whatsapp_notification(to_number: str, message: str) -> dict:
    """
    Sends a WhatsApp message via Twilio Sandbox.
    to_number must be in E.164 format, e.g. "+919876543210".
    Both sender (sandbox) and receiver must have completed the Twilio
    'join <code>' sandbox step for this to succeed.
    """
    if not TWILIO_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_FROM:
        return {"success": False, "error": "Twilio credentials not configured in .env"}

    try:
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
            body=message
        )
        return {"success": True, "sid": msg.sid, "status": msg.status}
    except Exception as e:
        return {"success": False, "error": str(e)}


def build_trip_message(trip) -> str:
    """Compose a readable trip-summary message for the family member."""
    return (
        f"🚏 Trip Update\n"
        f"Traveler is heading to destination via {trip.selected_stop_name} "
        f"({trip.selected_stop_type.replace('_', ' ')}).\n"
        f"Vehicle: {trip.vehicle_type}\n"
        f"Fare: ₹{trip.fare}\n"
        f"Estimated wait: {trip.estimated_wait_minutes} min\n"
        f"Trip ID: {trip.trip_id}"
    )