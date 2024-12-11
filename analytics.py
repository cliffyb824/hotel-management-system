from flask import Blueprint, jsonify, request
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from models import db, Room, Reservation, Payment, HousekeepingTask
import pandas as pd

analytics = Blueprint('analytics', __name__)

@analytics.route('/api/analytics/occupancy')
@login_required
def get_occupancy_stats():
    """Get room occupancy statistics"""
    try:
        today = datetime.utcnow().date()
        thirty_days_ago = today - timedelta(days=30)
        
        # Daily occupancy for the last 30 days
        daily_occupancy = db.session.query(
            func.date(Reservation.check_in).label('date'),
            func.count(Reservation.id).label('occupied_rooms')
        ).filter(
            Reservation.check_in >= thirty_days_ago,
            Reservation.status.in_(['checked_in', 'checked_out'])
        ).group_by(func.date(Reservation.check_in)).all()
        
        total_rooms = Room.query.count()
        
        occupancy_data = [{
            'date': day.date.isoformat(),
            'occupancy_rate': (day.occupied_rooms / total_rooms) * 100
        } for day in daily_occupancy]
        
        return jsonify(occupancy_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics.route('/api/analytics/revenue')
@login_required
def get_revenue_stats():
    """Get revenue statistics"""
    try:
        # Get revenue by month
        monthly_revenue = db.session.query(
            func.strftime('%Y-%m', Payment.payment_date).label('month'),
            func.sum(Payment.amount).label('revenue')
        ).filter(
            Payment.status == 'completed'
        ).group_by(func.strftime('%Y-%m', Payment.payment_date)).all()
        
        # Get revenue by room type
        revenue_by_room = db.session.query(
            Room.room_type,
            func.sum(Reservation.total_amount).label('revenue')
        ).join(Reservation).filter(
            Reservation.status.in_(['checked_in', 'checked_out'])
        ).group_by(Room.room_type).all()
        
        return jsonify({
            'monthly_revenue': [{
                'month': month.month,
                'revenue': float(month.revenue)
            } for month in monthly_revenue],
            'revenue_by_room_type': [{
                'room_type': room.room_type,
                'revenue': float(room.revenue)
            } for room in revenue_by_room]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics.route('/api/analytics/guest-insights')
@login_required
def get_guest_insights():
    """Get guest behavior insights"""
    try:
        # Average length of stay
        avg_stay = db.session.query(
            func.avg(
                func.julianday(Reservation.check_out) - 
                func.julianday(Reservation.check_in)
            ).label('avg_stay')
        ).filter(
            Reservation.status.in_(['checked_in', 'checked_out'])
        ).scalar()
        
        # Popular room types
        popular_rooms = db.session.query(
            Room.room_type,
            func.count(Reservation.id).label('bookings')
        ).join(Reservation).group_by(Room.room_type).all()
        
        # Booking sources distribution
        booking_sources = db.session.query(
            Reservation.booking_source,
            func.count(Reservation.id).label('count')
        ).group_by(Reservation.booking_source).all()
        
        return jsonify({
            'average_stay': float(avg_stay) if avg_stay else 0,
            'popular_room_types': [{
                'room_type': room.room_type,
                'bookings': room.bookings
            } for room in popular_rooms],
            'booking_sources': [{
                'source': source.booking_source,
                'count': source.count
            } for source in booking_sources]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics.route('/api/analytics/housekeeping-efficiency')
@login_required
def get_housekeeping_efficiency():
    """Get housekeeping efficiency metrics"""
    try:
        # Average time to complete tasks
        avg_completion_time = db.session.query(
            func.avg(
                func.julianday(HousekeepingTask.completed_at) - 
                func.julianday(HousekeepingTask.created_at)
            ).label('avg_time')
        ).filter(
            HousekeepingTask.status == 'completed'
        ).scalar()
        
        # Tasks by priority
        tasks_by_priority = db.session.query(
            HousekeepingTask.priority,
            func.count(HousekeepingTask.id).label('count')
        ).group_by(HousekeepingTask.priority).all()
        
        # Staff performance
        staff_performance = db.session.query(
            HousekeepingTask.assigned_to,
            func.count(HousekeepingTask.id).label('total_tasks'),
            func.sum(case([(HousekeepingTask.status == 'completed', 1)], else_=0)).label('completed_tasks')
        ).group_by(HousekeepingTask.assigned_to).all()
        
        return jsonify({
            'average_completion_time': float(avg_completion_time) if avg_completion_time else 0,
            'tasks_by_priority': [{
                'priority': task.priority,
                'count': task.count
            } for task in tasks_by_priority],
            'staff_performance': [{
                'staff_member': perf.assigned_to,
                'total_tasks': perf.total_tasks,
                'completed_tasks': perf.completed_tasks,
                'completion_rate': (perf.completed_tasks / perf.total_tasks * 100) if perf.total_tasks > 0 else 0
            } for perf in staff_performance]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics.route('/api/analytics/export-report', methods=['POST'])
@login_required
def export_report():
    """Export analytics report as Excel"""
    try:
        data = request.json
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        
        # Create a Pandas Excel writer
        writer = pd.ExcelWriter('hotel_analytics_report.xlsx', engine='xlsxwriter')
        
        # Reservations data
        reservations_df = pd.read_sql(
            db.session.query(
                Reservation.id,
                Reservation.guest_name,
                Reservation.check_in,
                Reservation.check_out,
                Reservation.total_amount,
                Reservation.status,
                Room.room_number,
                Room.room_type
            ).join(Room).filter(
                Reservation.check_in.between(start_date, end_date)
            ).statement,
            db.session.bind
        )
        reservations_df.to_excel(writer, sheet_name='Reservations', index=False)
        
        # Revenue data
        revenue_df = pd.read_sql(
            db.session.query(
                Payment.payment_date,
                Payment.amount,
                Payment.payment_method,
                Reservation.guest_name,
                Room.room_number
            ).join(Reservation).join(Room).filter(
                Payment.payment_date.between(start_date, end_date),
                Payment.status == 'completed'
            ).statement,
            db.session.bind
        )
        revenue_df.to_excel(writer, sheet_name='Revenue', index=False)
        
        # Housekeeping data
        housekeeping_df = pd.read_sql(
            db.session.query(
                HousekeepingTask.created_at,
                HousekeepingTask.completed_at,
                HousekeepingTask.status,
                HousekeepingTask.assigned_to,
                HousekeepingTask.priority,
                Room.room_number
            ).join(Room).filter(
                HousekeepingTask.created_at.between(start_date, end_date)
            ).statement,
            db.session.bind
        )
        housekeeping_df.to_excel(writer, sheet_name='Housekeeping', index=False)
        
        writer.save()
        
        return jsonify({'message': 'Report generated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
