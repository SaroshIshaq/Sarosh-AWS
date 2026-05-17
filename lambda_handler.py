"""
AWS Lambda Handler for UniEvent
Serverless Python deployment using AWS Lambda + API Gateway
Developed by: Sarosh Ishaq (Reg: 2023640)
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Tuple

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize AWS clients
s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')
dynamodb = boto3.resource('dynamodb')

# CloudWatch and X-Ray
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Configuration
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'unievent-media-2022123-giki')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'UniEventCache')
TICKETMASTER_API_URL = 'https://app.ticketmaster.com/discovery/v2/events.json'

# Developer Information
DEVELOPER_NAME = "Sarosh Ishaq"
REGISTRATION_NO = "2023640"


class TicketmasterAPIHandler:
    """Handle Ticketmaster API calls"""
    
    @staticmethod
    @tracer.capture_method
    def fetch_events(api_key: str) -> list:
        """Fetch events from Ticketmaster"""
        try:
            params = {
                'apikey': api_key,
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
                            'description': event.get('description', 'No description'),
                            'date': event.get('dates', {}).get('start', {}).get('dateTime', 'TBD'),
                            'venue': event.get('_embedded', {}).get('venues', [{}])[0].get('name', 'TBD'),
                            'city': event.get('_embedded', {}).get('venues', [{}])[0].get('city', {}).get('name', 'TBD'),
                            'image': event.get('images', [{}])[0].get('url', ''),
                            'url': event.get('url', '#'),
                            'ticketStatus': event.get('dates', {}).get('status', {}).get('code', 'Unknown')
                        }
                        events.append(event_obj)
                    except (KeyError, IndexError, TypeError):
                        continue
            
            logger.info(f'Fetched {len(events)} events from Ticketmaster')
            return events
        
        except Exception as e:
            logger.exception(f'Error fetching Ticketmaster events: {e}')
            return []


class DynamoDBCache:
    """Handle DynamoDB caching"""
    
    @staticmethod
    @tracer.capture_method
    def get_cached_events() -> list:
        """Get events from DynamoDB cache"""
        try:
            table = dynamodb.Table(DYNAMODB_TABLE)
            response = table.get_item(Key={'id': 'events'})
            
            if 'Item' in response:
                return response['Item'].get('events', [])
            return []
        except Exception as e:
            logger.exception(f'Error retrieving from DynamoDB: {e}')
            return []
    
    @staticmethod
    @tracer.capture_method
    def cache_events(events: list) -> bool:
        """Store events in DynamoDB"""
        try:
            table = dynamodb.Table(DYNAMODB_TABLE)
            table.put_item(
                Item={
                    'id': 'events',
                    'events': events,
                    'timestamp': int(datetime.now().timestamp()),
                    'ttl': int(datetime.now().timestamp()) + (6 * 3600),
                    'developer': DEVELOPER_NAME,
                    'registrationNo': REGISTRATION_NO
                }
            )
            logger.info(f'Cached {len(events)} events in DynamoDB')
            return True
        except Exception as e:
            logger.exception(f'Error caching to DynamoDB: {e}')
            return False


def get_api_key(parameter_name: str = '/unievent/ticketmaster-api-key') -> str:
    """Retrieve API key from Parameter Store"""
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.exception(f'Error retrieving API key: {e}')
        raise Exception('Unable to retrieve API credentials')


@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler for API Gateway requests
    """
    
    # Extract request details
    http_method = event.get('httpMethod')
    path = event.get('path')
    query_params = event.get('queryStringParameters', {}) or {}
    
    logger.info(f'Request: {http_method} {path}')
    metrics.add_metric(name='RequestCount', unit='Count', value=1)
    
    try:
        # Route requests
        if path == '/health' and http_method == 'GET':
            return health_check()
        
        elif path == '/api/events' and http_method == 'GET':
            return get_events()
        
        elif path == '/api/search' and http_method == 'GET':
            query = query_params.get('q', '') if query_params else ''
            return search_events(query)
        
        elif path == '/api/refresh-events' and http_method == 'POST':
            return refresh_events()
        
        elif path == '/api/status' and http_method == 'GET':
            return get_status()
        
        elif path == '/api/developer' and http_method == 'GET':
            return get_developer_info()
        
        else:
            return error_response(404, 'Endpoint not found')
    
    except Exception as e:
        logger.exception(f'Error handling request: {e}')
        metrics.add_metric(name='ErrorCount', unit='Count', value=1)
        return error_response(500, 'Internal server error')


def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    metrics.add_metric(name='HealthCheck', unit='Count', value=1)
    return success_response({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'UniEvent-Lambda',
        'developer': DEVELOPER_NAME,
        'registrationNo': REGISTRATION_NO
    })


def get_events() -> Dict[str, Any]:
    """Get all cached events"""
    events = DynamoDBCache.get_cached_events()
    metrics.add_metric(name='EventCount', unit='Count', value=len(events))
    
    return success_response({
        'status': 'success',
        'count': len(events),
        'developer': DEVELOPER_NAME,
        'registrationNo': REGISTRATION_NO,
        'events': events
    })


def search_events(query: str) -> Dict[str, Any]:
    """Search events"""
    if not query:
        return error_response(400, 'Search query required')
    
    events = DynamoDBCache.get_cached_events()
    query_lower = query.lower()
    
    results = [
        e for e in events
        if query_lower in e.get('name', '').lower() or
           query_lower in e.get('description', '').lower() or
           query_lower in e.get('venue', '').lower()
    ]
    
    metrics.add_metric(name='SearchCount', unit='Count', value=1)
    
    return success_response({
        'status': 'success',
        'query': query,
        'count': len(results),
        'developer': DEVELOPER_NAME,
        'registrationNo': REGISTRATION_NO,
        'events': results
    })


@tracer.capture_method
def refresh_events() -> Dict[str, Any]:
    """Refresh event cache"""
    try:
        api_key = get_api_key()
        events = TicketmasterAPIHandler.fetch_events(api_key)
        
        if events:
            DynamoDBCache.cache_events(events)
            metrics.add_metric(name='CacheRefresh', unit='Count', value=1)
        
        return success_response({
            'status': 'success',
            'message': 'Events refreshed successfully',
            'count': len(events),
            'developer': DEVELOPER_NAME,
            'registrationNo': REGISTRATION_NO
        })
    
    except Exception as e:
        logger.exception(f'Error refreshing events: {e}')
        return error_response(500, str(e))


def get_status() -> Dict[str, Any]:
    """Get system status"""
    events = DynamoDBCache.get_cached_events()
    
    return success_response({
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'cachedEvents': len(events),
        's3Bucket': S3_BUCKET_NAME,
        'dynamoDBTable': DYNAMODB_TABLE,
        'region': os.environ.get('AWS_REGION', 'us-east-1'),
        'developer': DEVELOPER_NAME,
        'registrationNo': REGISTRATION_NO
    })


def get_developer_info() -> Dict[str, Any]:
    """Get developer information"""
    return success_response({
        'status': 'success',
        'developer': {
            'name': DEVELOPER_NAME,
            'registrationNo': REGISTRATION_NO,
            'project': 'UniEvent - University Event Management System',
            'description': 'AWS Cloud Architecture with Python Lambda and Ticketmaster API Integration'
        }
    })


def success_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """Format success response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(data)
    }


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Format error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'status': 'error',
            'message': message,
            'developer': DEVELOPER_NAME,
            'registrationNo': REGISTRATION_NO
        })
    }
