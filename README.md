# UniEvent - University Event Management System

## Project Overview

**UniEvent** is a scalable university event management system built on AWS cloud infrastructure. The application integrates with the Ticketmaster API to fetch and display events, with a responsive web interface for users to search and register for events.

### Developer Information
- **Name:** Sarosh Ishaq
- **Registration Number:** 2023640
- **Project Type:** AWS Cloud Architecture with Python Flask
- **Academic Purpose:** Cloud Computing Assignment

## Technology Stack

### Frontend
- HTML5, CSS3, JavaScript
- Responsive design with modern UI
- Real-time event search and filtering

### Backend
- **Framework:** Python Flask
- **Serverless:** AWS Lambda with API Gateway
- **Storage:** AWS S3 (Event Media)
- **Cache:** AWS DynamoDB & in-memory caching
- **Configuration:** AWS Systems Manager Parameter Store
- **Monitoring:** AWS CloudWatch & X-Ray

### Cloud Services
- **AWS S3:** Media storage for event images
- **AWS Lambda:** Serverless event refresh function
- **AWS DynamoDB:** Event caching with TTL
- **AWS Systems Manager:** Secure credential management
- **AWS CloudWatch:** Logging and monitoring
- **AWS X-Ray:** Distributed tracing

## Features

### Core Functionality
1. **Event Discovery**
   - Browse all available events from Ticketmaster
   - Real-time event updates every 6 hours
   - View event details, dates, locations, and ticket status

2. **Event Search**
   - Full-text search across event names, descriptions, and venues
   - Instant filtering and results display
   - Search history support

3. **Event Management**
   - Manual event cache refresh
   - Automatic background refresh every 6 hours
   - Image optimization and S3 storage

4. **System Monitoring**
   - Health check endpoints
   - API status dashboard
   - Event cache statistics
   - Developer information endpoints

## API Endpoints

### Core Endpoints
- `GET /` - Home page with event listings
- `GET /health` - Health check status
- `GET /api/events` - Get all events
- `GET /api/events/<event_id>` - Get specific event
- `GET /api/search?q=<query>` - Search events
- `POST /api/refresh-events` - Manual cache refresh
- `GET /api/status` - System status
- `GET /api/developer` - Developer information

## Project Structure

```
Sarosh-AWS/
├── index.html              # Frontend HTML template
├── app.py                  # Flask application
├── lambda_handler.py       # AWS Lambda serverless handler
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Installation & Setup

### Local Development

1. **Clone Repository**
   ```bash
   git clone https://github.com/SaroshIshaq/Sarosh-AWS.git
   cd Sarosh-AWS
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   ```bash
   export AWS_REGION=us-east-1
   export S3_BUCKET_NAME=your-bucket-name
   export NODE_ENV=development
   export PORT=3000
   ```

4. **Run Flask Application**
   ```bash
   python app.py
   ```

5. **Access Application**
   - Open browser: `http://localhost:3000`

### AWS Lambda Deployment

1. **Package Application**
   ```bash
   pip install -r requirements.txt -t .
   zip -r lambda_function.zip .
   ```

2. **Deploy to AWS Lambda**
   - Upload `lambda_function.zip` to Lambda console
   - Set handler to `lambda_handler.lambda_handler`
   - Configure environment variables
   - Create API Gateway integration

## Configuration

### Environment Variables
```bash
AWS_REGION              # AWS region (default: us-east-1)
S3_BUCKET_NAME         # S3 bucket for media (default: unievent-media-2022123-giki)
DYNAMODB_TABLE         # DynamoDB table name (default: UniEventCache)
NODE_ENV               # Environment mode (development/production)
PORT                   # Server port (default: 3000)
TICKETMASTER_API_KEY   # Stored in Parameter Store
```

### AWS Parameter Store
- `/unievent/ticketmaster-api-key` - Encrypted API credentials

## Caching Strategy

- **Cache Duration:** 6 hours
- **Storage:** In-memory (Flask) / DynamoDB (Lambda)
- **Auto-refresh:** Scheduled every 6 hours
- **Manual Refresh:** Available via `/api/refresh-events` endpoint

## Performance Optimizations

1. **Image Optimization**
   - Async image downloads from Ticketmaster
   - S3 storage with metadata
   - Fallback to default images

2. **Caching**
   - 6-hour TTL for event data
   - Background refresh threads
   - Non-blocking image uploads

3. **API Rate Limiting**
   - Configured per Ticketmaster guidelines
   - Efficient parameter usage

## Security Features

- **Credentials Management:** AWS Parameter Store with encryption
- **CORS:** Enabled for cross-origin requests
- **Error Handling:** Comprehensive logging without exposing sensitive data
- **AWS IAM:** Role-based access control for resources

## Monitoring & Logging

- **CloudWatch Logs:** Structured logging with timestamps
- **X-Ray Tracing:** End-to-end request tracing
- **Metrics:** RequestCount, ErrorCount, EventCount, SearchCount
- **Health Checks:** Regular endpoint monitoring

## Future Enhancements

1. User authentication and registration
2. Event bookmarking and favorites
3. Email notifications for events
4. Social sharing features
5. Advanced filtering (category, price, date range)
6. Mobile app (iOS/Android)

## Troubleshooting

### Common Issues

**1. Ticketmaster API Key Not Found**
- Verify parameter exists in AWS Parameter Store
- Check IAM permissions for SSM access

**2. S3 Upload Failures**
- Verify bucket name and permissions
- Check AWS credentials

**3. DynamoDB Connection Issues**
- Verify table exists and region matches
- Check IAM DynamoDB permissions

## Dependencies

- **Flask** - Web framework
- **boto3** - AWS SDK
- **requests** - HTTP library
- **aws-lambda-powertools** - Lambda utilities
- **Python 3.9+**

## Contributing

This is an academic project. For modifications or improvements, please create a pull request with:
- Clear description of changes
- Updated documentation
- Test coverage

## Acknowledgments

- Ticketmaster API for event data
- AWS documentation and best practices
- Flask and boto3 communities

## License

This project is created for academic purposes as part of cloud computing coursework.

---

**Last Updated:** May 2026
**Developer:** Sarosh Ishaq (2023640)
**Status:** Active Development
