from flask_mail import Mail, Message
from threading import Thread
from flask import current_app, render_template_string

mail = Mail()

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, recipient, template, **kwargs):
    """Send an email asynchronously"""
    msg = Message(subject,
                 sender=current_app.config['MAIL_USERNAME'],
                 recipients=[recipient])
    
    msg.html = render_template_string(template, **kwargs)
    
    Thread(target=send_async_email,
           args=(current_app._get_current_object(), msg)).start()

def send_booking_confirmation(booking):
    """Send booking confirmation email"""
    template = """
    <h2>Booking Confirmation</h2>
    <p>Dear {{ booking.guest_name }},</p>
    <p>Your booking has been confirmed:</p>
    <ul>
        <li>Room: {{ booking.room.room_number }}</li>
        <li>Check-in: {{ booking.check_in.strftime('%Y-%m-%d') }}</li>
        <li>Check-out: {{ booking.check_out.strftime('%Y-%m-%d') }}</li>
        <li>Total Amount: ${{ "%.2f"|format(booking.total_amount) }}</li>
    </ul>
    <p>Thank you for choosing our hotel!</p>
    """
    
    send_email(
        'Booking Confirmation',
        booking.guest_email,
        template,
        booking=booking
    )

def send_cancellation_notification(booking):
    """Send booking cancellation notification"""
    template = """
    <h2>Booking Cancellation</h2>
    <p>Dear {{ booking.guest_name }},</p>
    <p>Your booking has been cancelled:</p>
    <ul>
        <li>Room: {{ booking.room.room_number }}</li>
        <li>Check-in: {{ booking.check_in.strftime('%Y-%m-%d') }}</li>
        <li>Check-out: {{ booking.check_out.strftime('%Y-%m-%d') }}</li>
    </ul>
    <p>If you did not request this cancellation, please contact us immediately.</p>
    """
    
    send_email(
        'Booking Cancellation',
        booking.guest_email,
        template,
        booking=booking
    )
