import requests
from datetime import datetime, timedelta
from app import db, Room, Reservation, OTAChannel, OTAReservation

class OTASync:
    def __init__(self, channel_id):
        self.channel = OTAChannel.query.get(channel_id)
        if not self.channel:
            raise ValueError("Invalid OTA channel ID")

    def sync_availability(self):
        """Sync room availability with OTA"""
        rooms = Room.query.all()
        available_rooms = []
        
        for room in rooms:
            # Check existing reservations
            is_available = self._check_room_availability(room)
            if is_available:
                available_rooms.append({
                    'room_id': room.id,
                    'room_type': room.room_type,
                    'rate': room.price
                })
        
        # TODO: Implement actual API call to OTA
        # This is a placeholder for the actual API implementation
        return self._update_ota_availability(available_rooms)

    def sync_reservations(self):
        """Sync reservations from OTA"""
        # TODO: Implement actual API call to OTA
        # This is a placeholder for the actual API implementation
        new_bookings = self._get_new_ota_bookings()
        
        for booking in new_bookings:
            self._create_reservation_from_ota(booking)

    def sync_cancellations(self):
        """Sync cancellations from OTA"""
        # TODO: Implement actual API call to OTA
        # This is a placeholder for the actual API implementation
        cancelled_bookings = self._get_ota_cancellations()
        
        for booking in cancelled_bookings:
            self._process_ota_cancellation(booking)

    def _check_room_availability(self, room):
        """Check if a room is available for the next 30 days"""
        today = datetime.now().date()
        thirty_days = today + timedelta(days=30)
        
        existing_reservations = Reservation.query.filter(
            Reservation.room_id == room.id,
            Reservation.check_out >= today,
            Reservation.check_in <= thirty_days,
            Reservation.status.in_(['reserved', 'checked_in'])
        ).all()
        
        # Room is considered available if there are no overlapping reservations
        return len(existing_reservations) == 0

    def _update_ota_availability(self, available_rooms):
        """Update room availability on OTA platform"""
        if self.channel.name == 'Booking.com':
            # Booking.com API endpoint (placeholder)
            api_url = 'https://distribution-xml.booking.com/2.0/json/availability'
            headers = {
                'Authorization': f'Basic {self.channel.api_key}',
                'Content-Type': 'application/json'
            }
            
            # Format data according to Booking.com API specifications
            payload = {
                'rooms': available_rooms
            }
            
            # TODO: Implement actual API call
            # response = requests.post(api_url, json=payload, headers=headers)
            # return response.json()
            return True

    def _get_new_ota_bookings(self):
        """Get new bookings from OTA platform"""
        if self.channel.name == 'Booking.com':
            # Booking.com API endpoint (placeholder)
            api_url = 'https://distribution-xml.booking.com/2.0/json/reservations'
            
            # TODO: Implement actual API call
            # Return placeholder data for now
            return []

    def _create_reservation_from_ota(self, booking_data):
        """Create a new reservation from OTA booking data"""
        try:
            # Create main reservation
            reservation = Reservation(
                guest_name=booking_data.get('guest_name'),
                room_id=booking_data.get('room_id'),
                check_in=datetime.strptime(booking_data.get('check_in'), '%Y-%m-%d').date(),
                check_out=datetime.strptime(booking_data.get('check_out'), '%Y-%m-%d').date(),
                total_amount=booking_data.get('total_amount'),
                booking_source=self.channel.name.lower(),
                is_ota_booking=True,
                status='reserved'
            )
            db.session.add(reservation)
            db.session.flush()  # Get reservation ID
            
            # Create OTA reservation record
            ota_reservation = OTAReservation(
                reservation_id=reservation.id,
                ota_channel_id=self.channel.id,
                ota_booking_id=booking_data.get('ota_booking_id'),
                ota_booking_status='confirmed',
                commission_amount=booking_data.get('commission_amount'),
                net_amount=booking_data.get('net_amount')
            )
            db.session.add(ota_reservation)
            db.session.commit()
            
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error creating reservation from OTA: {str(e)}")
            return False

    def _process_ota_cancellation(self, booking_data):
        """Process cancellation from OTA"""
        try:
            ota_reservation = OTAReservation.query.filter_by(
                ota_booking_id=booking_data.get('ota_booking_id')
            ).first()
            
            if ota_reservation:
                reservation = ota_reservation.reservation
                reservation.status = 'cancelled'
                ota_reservation.ota_booking_status = 'cancelled'
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            print(f"Error processing OTA cancellation: {str(e)}")
            return False
