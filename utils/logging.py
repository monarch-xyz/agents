import logging

def setup_logging():
    """Configure logging for the application"""
    # Set up root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Disable noisy loggers
    logging.getLogger('gql.transport.aiohttp').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.client').setLevel(logging.WARNING)
