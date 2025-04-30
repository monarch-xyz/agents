# Morpho Automation Service

[![Tests](https://github.com/YOUR_USERNAME/agent-backend/actions/workflows/test.yml/badge.svg)](https://github.com/YOUR_USERNAME/agent-backend/actions/workflows/test.yml)

This service automates fund reallocation for users who have authorized the bot. It runs periodically to:
1. Fetch blockchain data
2. Query Morpho API and Monarch subquery
3. Analyze data
4. Execute reallocation transactions

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your configuration:
```
# API endpoints
MORPHO_API_ENDPOINT=your_endpoint

# Blockchain configuration
WEB3_PROVIDER_URL=your_provider_url
PRIVATE_KEY=your_private_key
```

3. Run the service:
```bash
python main.py
```

## Local Development

1. Create and activate a virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory:
```env
# API endpoints
MONARCH_SUBQUERY_ENDPOINT=your_endpoint

# Blockchain configuration
WEB3_PROVIDER_URL=your_provider_url
PRIVATE_KEY=your_private_key

# Optional: Set to 'development' for more verbose logging
ENVIRONMENT=development
```

4. Run the service:
```bash
# Run directly with Python
python main.py
```

5. Check the logs:
- The service will create log output in the console
- If running in background, check `output.log`

## Development Tips

- The service runs every 6 hours by default. You can modify this in `main.py`
- To stop the background process:
  ```bash
  # Find the process
  ps aux | grep "python main.py"
  
  # Kill it using the process ID
  kill <process_id>
  ```
- For debugging, you can modify the schedule in `main.py` to run more frequently
- Check the logs for any errors or issues

## Architecture

The service is designed with modularity in mind:
- `main.py`: Entry point and scheduler
- `services/`: Core business logic
- `clients/`: API clients for external services
- `models/`: Data models
- `utils/`: Helper functions
