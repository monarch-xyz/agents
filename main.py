import schedule
import time
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
    
    # Schedule the job to run every 6 hours
    schedule.every(6).hours.do(run_automation)
    
    # Run once immediately on startup
    logging.info("Starting initial automation run...")
    run_automation()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute for pending jobs

if __name__ == "__main__":
    main()
