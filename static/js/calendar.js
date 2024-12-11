document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('room-calendar');
    
    if (calendarEl) {
        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek'
            },
            events: '/api/calendar-events',
            eventClick: function(info) {
                showReservationDetails(info.event.id);
            },
            eventContent: function(arg) {
                return {
                    html: `
                        <div class="fc-content">
                            <div class="fc-title">${arg.event.title}</div>
                            <div class="fc-description">${arg.event.extendedProps.room}</div>
                        </div>
                    `
                };
            }
        });
        
        calendar.render();
    }
});

function showReservationDetails(reservationId) {
    fetch(`/api/reservations/${reservationId}`)
        .then(response => response.json())
        .then(data => {
            const modal = new bootstrap.Modal(document.getElementById('reservationModal'));
            document.getElementById('modalReservationDetails').innerHTML = `
                <p><strong>Guest:</strong> ${data.guest_name}</p>
                <p><strong>Room:</strong> ${data.room_number}</p>
                <p><strong>Check-in:</strong> ${new Date(data.check_in).toLocaleDateString()}</p>
                <p><strong>Check-out:</strong> ${new Date(data.check_out).toLocaleDateString()}</p>
                <p><strong>Status:</strong> ${data.status}</p>
            `;
            modal.show();
        })
        .catch(error => console.error('Error:', error));
}
