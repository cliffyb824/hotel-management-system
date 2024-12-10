from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    room_type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='available')  # available, occupied, maintenance
    reservations = db.relationship('Reservation', backref='room', lazy=True)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guest_name = db.Column(db.String(100), nullable=False)
    guest_email = db.Column(db.String(120))
    guest_phone = db.Column(db.String(20))
    guest_address = db.Column(db.String(200))
    id_type = db.Column(db.String(50))  # passport, driver's license, etc.
    id_number = db.Column(db.String(50))
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=False)
    actual_check_in = db.Column(db.DateTime)
    actual_check_out = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='reserved')  # reserved, checked_in, checked_out, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    special_requests = db.Column(db.Text)
    number_of_guests = db.Column(db.Integer, default=1)
    payments = db.relationship('Payment', backref='reservation', lazy=True)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservation.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50), nullable=False)  # cash, credit_card, debit_card
    status = db.Column(db.String(20), default='completed')  # completed, pending, failed
    transaction_id = db.Column(db.String(100), unique=True)
    notes = db.Column(db.String(200))

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
        if user and user.password == password:  # In production, use proper password hashing
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    rooms = Room.query.all()
    reservations = Reservation.query.order_by(Reservation.created_at.desc()).limit(5).all()
    return render_template('dashboard.html', rooms=rooms, reservations=reservations)

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
        total_paid = sum(payment.amount for payment in reservation.payments)
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
        
    total_paid = sum(payment.amount for payment in reservation.payments)
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
    reservations = Reservation.query.all()
    return jsonify([{
        'id': r.id,
        'guest_name': r.guest_name,
        'room': {
            'id': r.room.id,
            'room_number': r.room.room_number,
            'rate': r.room.price
        },
        'check_in': r.check_in.strftime('%Y-%m-%d'),
        'check_out': r.check_out.strftime('%Y-%m-%d'),
        'status': r.status,
        'total_amount': r.total_amount,
        'actual_check_in': r.actual_check_in.strftime('%Y-%m-%d %H:%M:%S') if r.actual_check_in else None,
        'actual_check_out': r.actual_check_out.strftime('%Y-%m-%d %H:%M:%S') if r.actual_check_out else None
    } for r in reservations])

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
    reservations = Reservation.query.all()
    return render_template('billing.html', reservations=reservations)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
