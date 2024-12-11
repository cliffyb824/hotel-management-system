from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config
from errors import register_error_handlers
from notifications import mail, send_booking_confirmation, send_cancellation_notification
from models import db, Room, Reservation, Payment, HousekeepingTask, OTAChannel, OTAReservation, User
from housekeeping import housekeeping
from analytics import analytics
from sqlalchemy import func

app = Flask(__name__)
app.config.from_object(config[os.getenv('FLASK_ENV', 'development')])

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail.init_app(app)

# Register blueprints
app.register_blueprint(housekeeping)
app.register_blueprint(analytics)

# Setup rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Register error handlers
register_error_handlers(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully.')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        # Get total rooms
        total_rooms = Room.query.count()
        
        # Get available rooms
        available_rooms = Room.query.filter_by(status='available').count()
        
        # Get occupied rooms
        occupied_rooms = Room.query.filter_by(status='occupied').count()
        
        # Get today's check-ins
        today = datetime.now().date()
        todays_checkins = Reservation.query.filter(
            func.date(Reservation.check_in) == today
        ).count()
        
        # Get recent reservations - order by id if created_at is not available
        recent_reservations = Reservation.query.order_by(
            Reservation.id.desc()
        ).limit(5).all()
        
        return render_template('dashboard.html',
            total_rooms=total_rooms,
            available_rooms=available_rooms,
            occupied_rooms=occupied_rooms,
            todays_checkins=todays_checkins,
            recent_reservations=recent_reservations
        )
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        # Return a simple dashboard if there's an error
        return render_template('dashboard.html',
            total_rooms=0,
            available_rooms=0,
            occupied_rooms=0,
            todays_checkins=0,
            recent_reservations=[]
        )

@app.route('/rooms')
@login_required
def rooms():
    rooms = Room.query.all()
    return render_template('rooms.html', rooms=rooms)

@app.route('/api/rooms', methods=['POST'])
@login_required
def add_room():
    data = request.get_json()
    room = Room(
        room_number=data['roomNumber'],
        room_type=data['roomType'],
        price=float(data['price']),
        status='available'
    )
    db.session.add(room)
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Room added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/rooms/<int:room_id>', methods=['DELETE'])
@login_required
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    db.session.delete(room)
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Room deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/rooms/<int:room_id>', methods=['GET'])
@login_required
def get_room(room_id):
    room = Room.query.get_or_404(room_id)
    return jsonify({
        'id': room.id,
        'roomNumber': room.room_number,
        'roomType': room.room_type,
        'price': room.price,
        'status': room.status
    })

@app.route('/api/rooms/<int:room_id>', methods=['PUT'])
@login_required
def update_room(room_id):
    room = Room.query.get_or_404(room_id)
    data = request.get_json()
    
    room.room_number = data['roomNumber']
    room.room_type = data['roomType']
    room.price = float(data['price'])
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Room updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/reservations')
@login_required
def reservations():
    reservations = Reservation.query.all()
    rooms = Room.query.filter_by(status='available').all()  # Only show available rooms
    return render_template('reservations.html', reservations=reservations, rooms=rooms)

@app.route('/api/reservations', methods=['POST'])
@login_required
def add_reservation():
    data = request.get_json()
    try:
        check_in = datetime.strptime(data['checkIn'], '%Y-%m-%d')
        check_out = datetime.strptime(data['checkOut'], '%Y-%m-%d')
        
        reservation = Reservation(
            guest_name=data['guestName'],
            guest_email=data.get('guestEmail'),
            guest_phone=data.get('guestPhone'),
            guest_address=data.get('guestAddress'),
            id_type=data.get('idType'),
            id_number=data.get('idNumber'),
            room_id=int(data['roomId']),
            check_in=check_in,
            check_out=check_out,
            status='reserved'
        )
        
        room = Room.query.get(data['roomId'])
        if room:
            room.status = 'occupied'
        
        db.session.add(reservation)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Reservation added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/reservations/<int:reservation_id>', methods=['GET'])
@login_required
def get_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    return jsonify({
        'id': reservation.id,
        'guestName': reservation.guest_name,
        'guestEmail': reservation.guest_email,
        'guestPhone': reservation.guest_phone,
        'guestAddress': reservation.guest_address,
        'idType': reservation.id_type,
        'idNumber': reservation.id_number,
        'roomId': reservation.room_id,
        'checkIn': reservation.check_in.strftime('%Y-%m-%d'),
        'checkOut': reservation.check_out.strftime('%Y-%m-%d'),
        'status': reservation.status
    })

@app.route('/api/reservations/<int:reservation_id>', methods=['PUT'])
@login_required
def update_reservation(reservation_id):
    data = request.get_json()
    reservation = Reservation.query.get_or_404(reservation_id)
    
    if 'guestName' in data:
        reservation.guest_name = data['guestName']
    if 'guestEmail' in data:
        reservation.guest_email = data['guestEmail']
    if 'guestPhone' in data:
        reservation.guest_phone = data['guestPhone']
    if 'guestAddress' in data:
        reservation.guest_address = data['guestAddress']
    if 'idType' in data:
        reservation.id_type = data['idType']
    if 'idNumber' in data:
        reservation.id_number = data['idNumber']
    if 'specialRequests' in data:
        reservation.special_requests = data['specialRequests']
    if 'numberOfGuests' in data:
        reservation.number_of_guests = int(data['numberOfGuests'])
    
    if 'roomId' in data:
        old_room = Room.query.get(reservation.room_id)
        new_room = Room.query.get(int(data['roomId']))
        
        if old_room.id != new_room.id:
            if reservation.status == 'checked_in':
                old_room.status = 'available'
                new_room.status = 'occupied'
            else:
                old_room.status = 'available'
                new_room.status = 'reserved'
            reservation.room_id = new_room.id
    
    if 'checkIn' in data:
        reservation.check_in = datetime.strptime(data['checkIn'], '%Y-%m-%d')
    if 'checkOut' in data:
        reservation.check_out = datetime.strptime(data['checkOut'], '%Y-%m-%d')
    
    try:
        db.session.commit()
        return jsonify({
            'id': reservation.id,
            'guestName': reservation.guest_name,
            'guestEmail': reservation.guest_email,
            'guestPhone': reservation.guest_phone,
            'guestAddress': reservation.guest_address,
            'idType': reservation.id_type,
            'idNumber': reservation.id_number,
            'roomId': reservation.room_id,
            'checkIn': reservation.check_in.strftime('%Y-%m-%d'),
            'checkOut': reservation.check_out.strftime('%Y-%m-%d'),
            'status': reservation.status,
            'specialRequests': reservation.special_requests,
            'numberOfGuests': reservation.number_of_guests
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/reservations/<int:reservation_id>/cancel', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    try:
        reservation.status = 'cancelled'
        room = Room.query.get(reservation.room_id)
        if room:
            room.status = 'available'
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Reservation cancelled successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/reservations/<int:reservation_id>/calculate-bill', methods=['GET'])
@login_required
def calculate_bill(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    try:
        days = (reservation.check_out - reservation.check_in).days
        total_amount = days * reservation.room.price
        reservation.total_amount = total_amount
        db.session.commit()
        
        amount_paid = sum(payment.amount for payment in reservation.payments if payment.status == 'completed')
        
        return jsonify({
            'success': True,
            'total_amount': total_amount,
            'amount_paid': amount_paid,
            'balance': total_amount - amount_paid,
            'days': days,
            'daily_rate': reservation.room.price
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/reservations/<int:reservation_id>/payments', methods=['POST'])
@login_required
def add_payment(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    data = request.get_json()
    
    try:
        transaction_id = f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{reservation_id}"
        
        payment = Payment(
            reservation_id=reservation_id,
            amount=float(data['amount']),
            payment_method=data['paymentMethod'],
            transaction_id=transaction_id,
            notes=data.get('notes', '')
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment recorded successfully',
            'transaction_id': transaction_id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/reservations/<int:reservation_id>/payments', methods=['GET'])
@login_required
def get_payments(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    payments = [{
        'id': payment.id,
        'amount': payment.amount,
        'payment_date': payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
        'payment_method': payment.payment_method,
        'status': payment.status,
        'transaction_id': payment.transaction_id,
        'notes': payment.notes
    } for payment in reservation.payments]
    
    return jsonify({
        'success': True,
        'payments': payments
    })

@app.route('/api/reservations/<int:reservation_id>/check-in', methods=['POST'])
@login_required
def check_in(reservation_id):
    try:
        reservation = Reservation.query.get_or_404(reservation_id)
        print(f"Checking in reservation {reservation_id}, current status: {reservation.status}")
        
        if reservation.status != 'reserved':
            return jsonify({'error': 'Reservation is not in a valid state for check-in'}), 400
        
        # Verify all required guest information is present
        missing_fields = []
        if not reservation.guest_email:
            missing_fields.append('Email')
        if not reservation.guest_phone:
            missing_fields.append('Phone')
        if not reservation.guest_address:
            missing_fields.append('Address')
        if not reservation.id_type:
            missing_fields.append('ID Type')
        if not reservation.id_number:
            missing_fields.append('ID Number')
        
        if missing_fields:
            return jsonify({'error': f"Missing required guest information: {', '.join(missing_fields)}"}), 400
        
        # Calculate total amount if not set
        if not reservation.total_amount:
            days = (reservation.check_out - reservation.check_in).days
            room = Room.query.get(reservation.room_id)
            reservation.total_amount = days * room.price
        
        # Check if there's any outstanding balance that needs to be paid
        total_paid = sum(payment.amount for payment in reservation.payments if payment.status == 'completed')
        
        minimum_payment = reservation.total_amount * 0.5
        
        print(f"Total amount: ${reservation.total_amount:.2f}")
        print(f"Total paid: ${total_paid:.2f}")
        print(f"Minimum required: ${minimum_payment:.2f}")
        
        if total_paid < minimum_payment:
            return jsonify({
                'error': f"Minimum payment required for check-in: ${minimum_payment:.2f}. Current payment: ${total_paid:.2f}"
            }), 400
        
        reservation.status = 'checked_in'
        reservation.actual_check_in = datetime.utcnow()
        
        room = Room.query.get(reservation.room_id)
        room.status = 'occupied'
        
        db.session.commit()
        print(f"Check-in successful for reservation {reservation_id}")
        
        return jsonify({
            'message': 'Check-in successful',
            'checkInTime': reservation.actual_check_in.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        print(f"Error during check-in: {str(e)}")
        db.session.rollback()
        return jsonify({'error': f"An error occurred during check-in: {str(e)}"}), 500

@app.route('/api/reservations/<int:reservation_id>/check-out', methods=['POST'])
@login_required
def check_out(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    
    if reservation.status != 'checked_in':
        return jsonify({'error': 'Reservation is not checked in'}), 400
        
    total_paid = sum(payment.amount for payment in reservation.payments if payment.status == 'completed')
    if total_paid < reservation.total_amount:
        return jsonify({
            'error': 'Outstanding balance must be paid before check-out',
            'balance': reservation.total_amount - total_paid
        }), 400
        
    reservation.status = 'checked_out'
    reservation.actual_check_out = datetime.utcnow()
    
    room = Room.query.get(reservation.room_id)
    room.status = 'available'
    
    db.session.commit()
    
    return jsonify({
        'message': 'Check-out successful',
        'checkOutTime': reservation.actual_check_out.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/reservations')
@login_required
def get_reservations():
    """Get all reservations with room details"""
    try:
        reservations = Reservation.query.join(Room).all()
        return jsonify([{
            'id': r.id,
            'guest_name': r.guest_name,
            'room_number': r.room.room_number,
            'check_in': r.check_in.strftime('%Y-%m-%d'),
            'check_out': r.check_out.strftime('%Y-%m-%d'),
            'status': r.status,
            'room_type': r.room.room_type,
            'total_amount': float(r.total_amount) if r.total_amount else 0
        } for r in reservations])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/details')
@login_required
def get_reservation_details(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    return jsonify({
        'id': reservation.id,
        'guest_name': reservation.guest_name,
        'guest_email': reservation.guest_email,
        'guest_phone': reservation.guest_phone,
        'guest_address': reservation.guest_address,
        'id_type': reservation.id_type,
        'id_number': reservation.id_number,
        'special_requests': reservation.special_requests,
        'number_of_guests': reservation.number_of_guests,
        'room': {
            'id': reservation.room.id,
            'number': reservation.room.room_number,
            'type': reservation.room.room_type,
            'rate': reservation.room.price
        },
        'check_in': reservation.check_in.strftime('%Y-%m-%d'),
        'check_out': reservation.check_out.strftime('%Y-%m-%d'),
        'actual_check_in': reservation.actual_check_in.strftime('%Y-%m-%d %H:%M:%S') if reservation.actual_check_in else None,
        'actual_check_out': reservation.actual_check_out.strftime('%Y-%m-%d %H:%M:%S') if reservation.actual_check_out else None,
        'status': reservation.status,
        'total_amount': reservation.total_amount
    })

@app.route('/guests')
@login_required
def guests():
    # Get all guests from reservations
    reservations = Reservation.query.all()
    return render_template('guests.html', reservations=reservations)

@app.route('/api/guests')
@login_required
def get_guests():
    reservations = Reservation.query.all()
    return jsonify([{
        'id': r.id,
        'guest_name': r.guest_name,
        'guest_email': r.guest_email,
        'guest_phone': r.guest_phone,
        'guest_address': r.guest_address,
        'id_type': r.id_type,
        'id_number': r.id_number,
        'special_requests': r.special_requests,
        'number_of_guests': r.number_of_guests,
        'check_in': r.check_in.strftime('%Y-%m-%d'),
        'check_out': r.check_out.strftime('%Y-%m-%d'),
        'status': r.status,
        'room_number': r.room.room_number if r.room else None
    } for r in reservations])

@app.route('/billing')
@login_required
def billing():
    # Get all reservations with their payment information
    reservations = Reservation.query.all()
    return render_template('billing.html', reservations=reservations)

@app.route('/api/billing')
@login_required
def get_billing():
    reservations = Reservation.query.all()
    return jsonify([{
        'id': r.id,
        'guest_name': r.guest_name,
        'room_number': r.room.room_number,
        'room_type': r.room.room_type,
        'room_rate': r.room.price,
        'check_in': r.check_in.strftime('%Y-%m-%d'),
        'check_out': r.check_out.strftime('%Y-%m-%d'),
        'total_amount': r.total_amount,
        'status': r.status,
        'payment_status': 'Paid' if r.total_amount and r.total_amount > 0 else 'Pending'
    } for r in reservations])

@app.route('/api/billing/<int:reservation_id>/details')
@login_required
def get_billing_details(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    # Calculate number of nights
    nights = (reservation.check_out - reservation.check_in).days
    
    return jsonify({
        'id': reservation.id,
        'guest_name': reservation.guest_name,
        'room_number': reservation.room.room_number,
        'room_type': reservation.room.room_type,
        'room_rate': reservation.room.price,
        'check_in': reservation.check_in.strftime('%Y-%m-%d'),
        'check_out': reservation.check_out.strftime('%Y-%m-%d'),
        'nights': nights,
        'room_total': nights * reservation.room.price,
        'total_amount': reservation.total_amount,
        'status': reservation.status,
        'payment_status': 'Paid' if reservation.total_amount and reservation.total_amount > 0 else 'Pending'
    })

@app.route('/admin/management')
@login_required
def admin_management():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    admins = User.query.filter_by(is_admin=True).all()
    return render_template('admin_management.html', admins=admins)

@app.route('/admin/add', methods=['POST'])
@login_required
def add_admin():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required'})
    
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    new_admin = User(
        username=username,
        password=generate_password_hash(password, method='sha256'),
        is_admin=True
    )
    
    try:
        db.session.add(new_admin)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/delete/<int:admin_id>', methods=['POST'])
@login_required
def delete_admin(admin_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    admin = User.query.get_or_404(admin_id)
    
    # Prevent deleting the default admin
    if admin.username == 'admin':
        return jsonify({'success': False, 'message': 'Cannot delete default admin'})
    
    # Prevent self-deletion
    if admin.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot delete your own account'})
    
    try:
        db.session.delete(admin)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/reset-password/<int:admin_id>', methods=['POST'])
@login_required
def reset_admin_password(admin_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    admin = User.query.get_or_404(admin_id)
    password = request.form.get('password')
    
    if not password:
        return jsonify({'success': False, 'message': 'Password is required'})
    
    try:
        admin.password = generate_password_hash(password, method='sha256')
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/update/<int:admin_id>', methods=['POST'])
@login_required
def update_admin(admin_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    admin = User.query.get_or_404(admin_id)
    
    # Prevent updating the default admin
    if admin.username == 'admin':
        return jsonify({'success': False, 'message': 'Cannot modify default admin'})
    
    username = request.form.get('username')
    
    if not username:
        return jsonify({'success': False, 'message': 'Username is required'})
    
    # Check if username is already taken by another user
    existing_user = User.query.filter_by(username=username).first()
    if existing_user and existing_user.id != admin_id:
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    try:
        admin.username = username
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/api/room-types')
def api_get_room_types():
    """Get all unique room types"""
    room_types = db.session.query(Room.room_type, db.func.count(Room.id).label('count')).group_by(Room.room_type).all()
    return jsonify([{'id': i, 'name': room_type, 'count': count} for i, (room_type, count) in enumerate(room_types, 1)])

@app.route('/api/rooms')
@login_required
def get_rooms():
    """Get all rooms with their current status"""
    try:
        rooms = Room.query.all()
        return jsonify([{
            'id': room.id,
            'room_number': room.room_number,
            'room_type': room.room_type,
            'price': float(room.price),
            'status': room.status
        } for room in rooms])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reservations')
@login_required
def get_all_reservations():
    """Get all reservations with room details"""
    try:
        reservations = Reservation.query.join(Room).all()
        return jsonify([{
            'id': res.id,
            'guest_name': res.guest_name,
            'room_number': res.room.room_number,
            'check_in': res.check_in.strftime('%Y-%m-%d'),
            'check_out': res.check_out.strftime('%Y-%m-%d'),
            'status': res.status,
            'room_type': res.room.room_type,
            'total_amount': float(res.total_amount) if res.total_amount else 0
        } for res in reservations])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<int:room_id>')
def api_get_room(room_id):
    """Get a specific room"""
    room = Room.query.get_or_404(room_id)
    return jsonify({
        'id': room.id,
        'name': f'Room {room.room_number}',
        'type': room.room_type,
        'price': room.price,
        'status': room.status,
        'description': f'{room.room_type} room with all amenities',
        'image_url': f'/static/images/rooms/{room.room_type.lower().replace(" ", "_")}.jpg'
    })

@app.route('/api/check-availability', methods=['POST'])
def api_check_availability():
    """Check room availability based on dates and guest configuration"""
    try:
        data = request.json
        check_in = datetime.strptime(data['check_in'], '%Y-%m-%d')
        check_out = datetime.strptime(data['check_out'], '%Y-%m-%d')
        room_config = data.get('room_config', '1 Room, 2 Adults')
        
        # Parse room configuration
        room_count = int(room_config.split(' Room')[0])
        adults = int(room_config.split(', ')[1].split(' Adult')[0])
        guests_per_room = adults / room_count
        
        # Query available rooms
        available_rooms = []
        rooms = Room.query.all()
        
        for room in rooms:
            # Check if room has any overlapping reservations
            overlapping = Reservation.query.filter(
                Reservation.room_id == room.id,
                Reservation.status.in_(['reserved', 'checked_in']),
                Reservation.check_in < check_out,
                Reservation.check_out > check_in
            ).first()
            
            # Determine room capacity based on type
            room_capacity = 2 if 'Double' in room.room_type or 'Suite' in room.room_type else 1
            
            if not overlapping and room.status == 'available' and room_capacity >= guests_per_room:
                available_rooms.append({
                    'id': room.id,
                    'name': f'Room {room.room_number}',
                    'type': room.room_type,
                    'price': room.price,
                    'capacity': room_capacity,
                    'status': 'available',
                    'description': f'{room.room_type} room with all amenities',
                    'image_url': f'/static/images/rooms/{room.room_type.lower().replace(" ", "_")}.jpg'
                })
        
        # If multiple rooms requested, ensure we have enough rooms
        if room_count > 1 and len(available_rooms) < room_count:
            return jsonify({
                'error': f'Not enough rooms available for {room_config}. Only {len(available_rooms)} rooms available.'
            }), 400
            
        return jsonify(available_rooms)
        
    except ValueError as e:
        return jsonify({'error': 'Invalid date format or room configuration'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reservations', methods=['POST'])
def api_create_reservation():
    """Create a new reservation through API"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['guest_name', 'guest_email', 'guest_phone', 'room_id', 
                         'check_in', 'check_out']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Parse dates
        check_in = datetime.strptime(data['check_in'], '%Y-%m-%d')
        check_out = datetime.strptime(data['check_out'], '%Y-%m-%d')

        # Check if room exists and is available
        room = Room.query.get(data['room_id'])
        if not room:
            return jsonify({'error': 'Room not found'}), 404

        # Check for overlapping reservations
        overlapping = Reservation.query.filter(
            Reservation.room_id == room.id,
            Reservation.status.in_(['reserved', 'checked_in']),
            Reservation.check_in < check_out,
            Reservation.check_out > check_in
        ).first()

        if overlapping:
            return jsonify({'error': 'Room is not available for these dates'}), 400

        # Calculate total amount if not provided
        total_amount = data.get('total_amount', room.price * (check_out - check_in).days)

        # Create new reservation
        reservation = Reservation(
            guest_name=data['guest_name'],
            guest_email=data['guest_email'],
            guest_phone=data['guest_phone'],
            room_id=room.id,
            check_in=check_in,
            check_out=check_out,
            total_amount=total_amount,
            special_requests=data.get('special_requests', ''),
            booking_source=data.get('booking_source', 'online'),
            status='reserved'
        )

        db.session.add(reservation)
        db.session.commit()

        return jsonify({
            'success': True,
            'reservation_id': reservation.id,
            'message': 'Reservation created successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar-events')
@login_required
@limiter.limit("60 per minute")
def get_calendar_events():
    """Get all reservations for calendar view"""
    try:
        reservations = Reservation.query.all()
        events = []
        for reservation in reservations:
            status_colors = {
                'reserved': '#ffc107',  # warning
                'checked_in': '#28a745',  # success
                'checked_out': '#6c757d',  # secondary
                'cancelled': '#dc3545'  # danger
            }
            
            events.append({
                'id': reservation.id,
                'title': f"{reservation.guest_name}",
                'start': reservation.check_in.isoformat(),
                'end': reservation.check_out.isoformat(),
                'backgroundColor': status_colors.get(reservation.status, '#17a2b8'),
                'borderColor': status_colors.get(reservation.status, '#17a2b8'),
                'extendedProps': {
                    'room': f"Room {reservation.room.room_number}",
                    'status': reservation.status
                }
            })
        return jsonify(events)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>')
@login_required
@limiter.limit("60 per minute")
def get_reservation_api(reservation_id):
    """Get reservation details for API"""
    try:
        reservation = Reservation.query.get_or_404(reservation_id)
        return jsonify({
            'id': reservation.id,
            'guest_name': reservation.guest_name,
            'room_number': reservation.room.room_number,
            'check_in': reservation.check_in.isoformat(),
            'check_out': reservation.check_out.isoformat(),
            'status': reservation.status,
            'total_amount': float(reservation.total_amount),
            'guest_email': reservation.guest_email,
            'guest_phone': reservation.guest_phone,
            'special_requests': reservation.special_requests
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        try:
            # Drop all tables and recreate them
            db.drop_all()
            db.create_all()
            
            # Create default admin user
            admin_user = User(
                username='admin', 
                password=generate_password_hash('admin123', method='sha256'),
                is_admin=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin_user)
            
            # Create some sample rooms
            rooms = [
                Room(room_number='101', room_type='Standard', price=100.0),
                Room(room_number='102', room_type='Standard', price=100.0),
                Room(room_number='201', room_type='Deluxe', price=150.0),
                Room(room_number='202', room_type='Deluxe', price=150.0),
                Room(room_number='301', room_type='Suite', price=200.0)
            ]
            for room in rooms:
                db.session.add(room)
            
            db.session.commit()
            print("Database initialized with default admin user and sample rooms")
            print("Admin credentials - username: admin, password: admin123")
            
            # Start OTA sync scheduler
            from scheduled_tasks import start_scheduler
            start_scheduler()
            
            app.run(debug=True)
            
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            raise
