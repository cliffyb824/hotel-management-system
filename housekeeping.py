from flask import Blueprint, jsonify, request
from flask_login import login_required
from datetime import datetime, timedelta
from models import db, Room, Reservation, HousekeepingTask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

housekeeping = Blueprint('housekeeping', __name__)
limiter = Limiter(key_func=get_remote_address)

@housekeeping.route('/api/housekeeping/tasks', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def get_tasks():
    """Get all housekeeping tasks"""
    try:
        tasks = HousekeepingTask.query.order_by(HousekeepingTask.created_at.desc()).all()
        return jsonify([{
            'id': task.id,
            'room_number': task.room.room_number,
            'status': task.status,
            'assigned_to': task.assigned_to,
            'notes': task.notes,
            'created_at': task.created_at.isoformat(),
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'priority': task.priority,
            'task_type': task.task_type
        } for task in tasks])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@housekeeping.route('/api/housekeeping/tasks', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def create_task():
    """Create a new housekeeping task"""
    try:
        data = request.json
        room = Room.query.get_or_404(data['room_id'])
        
        task = HousekeepingTask(
            room_id=room.id,
            status='pending',
            assigned_to=data.get('assigned_to'),
            notes=data.get('notes'),
            priority=data.get('priority', 'normal'),
            task_type=data.get('task_type', 'regular')
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            'message': 'Task created successfully',
            'task_id': task.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@housekeeping.route('/api/housekeeping/tasks/<int:task_id>', methods=['PUT'])
@login_required
@limiter.limit("30 per minute")
def update_task(task_id):
    """Update a housekeeping task"""
    try:
        task = HousekeepingTask.query.get_or_404(task_id)
        data = request.json
        
        if 'status' in data:
            task.status = data['status']
            if data['status'] == 'completed':
                task.completed_at = datetime.utcnow()
        
        if 'assigned_to' in data:
            task.assigned_to = data['assigned_to']
        if 'notes' in data:
            task.notes = data['notes']
        if 'priority' in data:
            task.priority = data['priority']
        
        db.session.commit()
        return jsonify({'message': 'Task updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@housekeeping.route('/api/housekeeping/schedule', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def get_schedule():
    """Get housekeeping schedule based on check-ins and check-outs"""
    try:
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        
        # Get rooms with check-outs today
        checkouts = Reservation.query.filter(
            Reservation.check_out.between(today, tomorrow),
            Reservation.status == 'checked_in'
        ).all()
        
        # Get rooms with check-ins today
        checkins = Reservation.query.filter(
            Reservation.check_in.between(today, tomorrow),
            Reservation.status == 'reserved'
        ).all()
        
        schedule = {
            'checkouts': [{
                'room_number': res.room.room_number,
                'guest_name': res.guest_name,
                'check_out': res.check_out.isoformat()
            } for res in checkouts],
            'checkins': [{
                'room_number': res.room.room_number,
                'guest_name': res.guest_name,
                'check_in': res.check_in.isoformat()
            } for res in checkins]
        }
        
        return jsonify(schedule)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
