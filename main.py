import logging
from dotenv import load_dotenv
from services.automation_service import AutomationService
import asyncio
from utils.logging import setup_logging

# Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)

def run_automation():
    """Main function to run the automation process"""
    try:
        service = AutomationService()
        asyncio.run(service.run())
    except Exception as e:
        logging.error(f"Error in automation run: {str(e)}", exc_info=True)

def main():
    setup_logging()  # Configure logging before anything else
    # Load environment variables
    load_dotenv()
    
    # Run automation once
    logging.info("Starting automation run...")
    run_automation()

if __name__ == "__main__":
    main()
