from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import pytz
from ota_sync import OTASync
from app import OTAChannel

def sync_ota_data():
    try:
        print("Starting OTA sync...")
        channels = OTAChannel.query.filter_by(is_active=True).all()
        for channel in channels:
            try:
                sync = OTASync(channel)
                sync.sync_availability()
                sync.sync_reservations()
                print(f"Successfully synced with {channel.name}")
            except Exception as e:
                print(f"Error syncing with {channel.name}: {str(e)}")
    except Exception as e:
        print(f"Error in OTA sync: {str(e)}")

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.UTC)
    
    # Add job to sync OTA data every 15 minutes
    scheduler.add_job(
        func=sync_ota_data,
        trigger=IntervalTrigger(minutes=15),
        id='ota_sync_job',
        name='Sync OTA Data',
        replace_existing=True
    )
    
    try:
        scheduler.start()
        print("OTA sync scheduler started successfully")
    except Exception as e:
        print(f"Error starting scheduler: {str(e)}")
    
    return scheduler
