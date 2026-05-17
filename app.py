"""
UniEvent - Scalable University Event Management System
Python Flask Application with AWS Integration
Developed by: Sarosh Ishaq (Reg: 2023640)
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from threading import Thread
import time

import requests
from flask import Flask, render_template, jsonify, request
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app initialization
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# AWS Clients
s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1'))
ssm_client = boto3.client('ssm', region_name=os.getenv('AWS_REGION', 'us-east-1'))

# Cache configuration
cached_events = []
last_fetch_time = None
CACHE_DURATION_HOURS = 6
CACHE_DURATION_SECONDS = CACHE_DURATION_HOURS * 3600
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'unievent-media-2022123-giki')
TICKETMASTER_API_URL = 'https://app.ticketmaster.com/discovery/v2/events.json'

# Developer Information
DEVELOPER_NAME = "Sarosh Ishaq"
REGISTRATION_NO = "2023640"


class TicketmasterAPI:
    """Handle Ticketmaster API integration"""
    
    def __init__(self):
        self.api_key = None
        self.load_api_key()
    
    def load_api_key(self):
        """Load API key from AWS Parameter Store"""
        try:
            response = ssm_client.get_parameter(
                Name='/unievent/ticketmaster-api-key',
                WithDecryption=True
            )
            self.api_key = response['Parameter']['Value']
            logger.info('✓ Ticketmaster API key loaded from Parameter Store')
        except ClientError as e:
            logger.error(f'✗ Error retrieving API key: {e}')
            raise Exception('Unable to retrieve API credentials')
    
    def fetch_events(self) -> List[Dict]:
        """Fetch events from Ticketmaster Discovery API"""
        try:
            if not self.api_key:
                self.load_api_key()
            
            params = {
                'apikey': self.api_key,
                'countryCode': 'US',
                'size': 20,
                'sort': 'date,asc'
            }
            
            response = requests.get(TICKETMASTER_API_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            if '_embedded' in data and 'events' in data['_embedded']:
                for event in data['_embedded']['events']:
                    try:
                        event_obj = {
                            'id': event.get('id'),
                            'name': event.get('name'),
                            'description': event.get('description', 'No description available'),
                            'date': event.get('dates', {}).get('start', {}).get('dateTime') or 
                                   event.get('dates', {}).get('start', {}).get('localDate') or 
                                   'Date TBD',
                            'venue': event.get('_embedded', {}).get('venues', [{}])[0].get('name', 'Venue TBD'),
                            'city': event.get('_embedded', {}).get('venues', [{}])[0].get('city', {}).get('name', 'City TBD'),
                            'image': event.get('images', [{}])[0].get('url', '/static/images/default-event.png'),
                            'url': event.get('url', '#'),
                            'ticketStatus': event.get('dates', {}).get('status', {}).get('code', 'Unknown')
                        }
                        events.append(event_obj)
                    except (KeyError, IndexError, TypeError) as e:
                        logger.warning(f'Error parsing event: {e}')
                        continue
            
            logger.info(f'✓ Successfully fetched {len(events)} events from Ticketmaster')
            return events
        
        except requests.RequestException as e:
            logger.error(f'✗ Error fetching events from Ticketmaster: {e}')
            return cached_events if cached_events else []


class S3Manager:
    """Handle S3 operations for media storage"""
    
    @staticmethod
    def download_image(image_url: str, timeout: int = 5) -> Optional[bytes]:
        """Download image from URL"""
        try:
            response = requests.get(image_url, timeout=timeout)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.error(f'Error downloading image from {image_url}: {e}')
            return None
    
    @staticmethod
    def upload_to_s3(event_id: str, event_name: str, image_data: bytes) -> Optional[str]:
        """Upload image to S3"""
        try:
            file_name = f'event-{event_id}-{int(time.time())}.jpg'
            s3_key = f'events/{file_name}'
            
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=image_data,
                ContentType='image/jpeg',
                Metadata={
                    'event-id': event_id,
                    'event-name': event_name[:50],
                    'developer': DEVELOPER_NAME,
                    'registration-no': REGISTRATION_NO
                }
            )
            
            logger.info(f'✓ Image uploaded to S3: {s3_key}')
            return f's3://{S3_BUCKET_NAME}/{s3_key}'
        
        except ClientError as e:
            logger.error(f'✗ Error uploading to S3: {e}')
            return None


def refresh_event_cache():
    """Refresh event cache from Ticketmaster API"""
    global cached_events, last_fetch_time
    
    logger.info(f'[{datetime.now().isoformat()}] Refreshing event cache...')
    
    try:
        tm_api = TicketmasterAPI()
        events = tm_api.fetch_events()
        
        # Non-blocking S3 image uploads
        if events:
            for event in events:
                if event['image'] and 'default-event' not in event['image']:
                    def upload_image_async(e):
                        image_data = S3Manager.download_image(e['image'])
                        if image_data:
                            s3_url = S3Manager.upload_to_s3(e['id'], e['name'], image_data)
                            if s3_url:
                                # Update cached event with S3 URL
                                for cached_event in cached_events:
                                    if cached_event['id'] == e['id']:
                                        cached_event['s3_image_url'] = s3_url
                    
                    # Run in background
                    Thread(target=upload_image_async, args=(event,), daemon=True).start()
        
        cached_events = events
        last_fetch_time = datetime.now()
        logger.info(f'✓ Successfully cached {len(events)} events')
    
    except Exception as e:
        logger.error(f'✗ Cache refresh error: {e}')


def scheduled_cache_refresh():
    """Scheduled background task for cache refresh"""
    while True:
        time.sleep(CACHE_DURATION_SECONDS)
        refresh_event_cache()


# Routes

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for ALB"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cachedEvents': len(cached_events),
        'developer': DEVELOPER_NAME,
        'registrationNo': REGISTRATION_NO,
        'uptime': time.time()
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Home page - display all events"""
    last_updated = last_fetch_time.strftime('%Y-%m-%d %H:%M:%S') if last_fetch_time else 'Not yet fetched'
    return render_template('index.html', events=cached_events, last_updated=last_updated)


@app.route('/api/events', methods=['GET'])
def get_events():
    """API endpoint - get all events"""
    return jsonify({
        'status': 'success',
        'count': len(cached_events),
        'lastUpdated': last_fetch_time.isoformat() if last_fetch_time else None,
        'developer': DEVELOPER_NAME,
        'registrationNo': REGISTRATION_NO,
        'events': cached_events
    }), 200


@app.route('/api/events/<event_id>', methods=['GET'])
def get_event(event_id):
    """API endpoint - get single event by ID"""
    event = next((e for e in cached_events if e['id'] == event_id), None)
    
    if not event:
        return jsonify({
            'status': 'error',
            'message': 'Event not found'
        }), 404
    
    return jsonify({
        'status': 'success',
        'event': event
    }), 200


@app.route('/api/search', methods=['GET'])
def search_events():
    """API endpoint - search events"""
    query = request.args.get('q', '').lower()
    
    if not query:
        return jsonify({
            'status': 'error',
            'message': 'Search query required'
        }), 400
    
    results = [
        event for event in cached_events
        if query in event['name'].lower() or
           query in event['description'].lower() or
           query in event['venue'].lower()
    ]
    
    return jsonify({
        'status': 'success',
        'query': query,
        'count': len(results),
        'events': results
    }), 200


@app.route('/api/refresh-events', methods=['POST'])
def manual_refresh():
    """API endpoint - manually trigger cache refresh"""
    try:
        refresh_event_cache()
        return jsonify({
            'status': 'success',
            'message': 'Events refreshed successfully',
            'count': len(cached_events),
            'developer': DEVELOPER_NAME,
            'registrationNo': REGISTRATION_NO
        }), 200
    except Exception as e:
        logger.error(f'Error during manual refresh: {e}')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/status', methods=['GET'])
def api_status():
    """API endpoint - get system status"""
    return jsonify({
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'cachedEvents': len(cached_events),
        'lastRefresh': last_fetch_time.isoformat() if last_fetch_time else None,
        'cacheExpiry': (last_fetch_time + timedelta(hours=CACHE_DURATION_HOURS)).isoformat() if last_fetch_time else None,
        's3Bucket': S3_BUCKET_NAME,
        'region': os.getenv('AWS_REGION', 'us-east-1'),
        'developer': DEVELOPER_NAME,
        'registrationNo': REGISTRATION_NO
    }), 200


@app.route('/api/developer', methods=['GET'])
def get_developer_info():
    """API endpoint - get developer information"""
    return jsonify({
        'status': 'success',
        'developer': {
            'name': DEVELOPER_NAME,
            'registrationNo': REGISTRATION_NO,
            'project': 'UniEvent - University Event Management System',
            'description': 'AWS Cloud Architecture with Python Flask and Ticketmaster API Integration'
        }
    }), 200


# Error handlers

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f'Internal server error: {error}')
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500


@app.before_request
def log_request():
    """Log incoming requests"""
    logger.debug(f'{request.method} {request.path}')


@app.after_request
def log_response(response):
    """Log outgoing responses"""
    logger.debug(f'{response.status_code} {request.path}')
    return response


# Application startup

def init_app():
    """Initialize application"""
    logger.info('═' * 60)
    logger.info('UniEvent Application Starting')
    logger.info(f'Developer: {DEVELOPER_NAME} | Reg: {REGISTRATION_NO}')
    logger.info('═' * 60)
    logger.info(f'Environment: {os.getenv("NODE_ENV", "development")}')
    logger.info(f'Port: {os.getenv("PORT", 3000)}')
    logger.info(f'AWS Region: {os.getenv("AWS_REGION", "us-east-1")}')
    logger.info(f'S3 Bucket: {S3_BUCKET_NAME}')
    
    # Initial event fetch
    refresh_event_cache()
    
    # Start scheduled cache refresh in background thread
    cache_thread = Thread(target=scheduled_cache_refresh, daemon=True)
    cache_thread.start()
    logger.info('✓ Event cache refresh scheduled every 6 hours')
    logger.info('═' * 60)


if __name__ == '__main__':
    # Initialize before starting
    init_app()
    
    # Get configuration
    port = int(os.getenv('PORT', 3000))
    debug = os.getenv('NODE_ENV', 'development') == 'development'
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=False  # Disable reloader when using threads
    )
