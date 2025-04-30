import logging
import os
from dotenv import load_dotenv
from services.automation_service import AutomationService
import asyncio
from utils.logging import setup_logging

# Initialize logger for the module
logger = logging.getLogger(__name__)

async def run_automation_for_network(chain_id: int):
    """Runs the automation process for a specific network."""
    logger.info(f"Starting automation run for chain ID: {chain_id}...")
    try:
        # Only pass the chain_id. Service will determine URLs.
        service = AutomationService(chain_id=chain_id)
        await service.run()
        logger.info(f"Finished automation run for chain ID: {chain_id}.")
    except ValueError as ve:
        # Catch specific configuration errors from service init
        logging.error(f"Configuration error for chain ID {chain_id}: {str(ve)}")
    except Exception as e:
        logging.error(f"Error in automation run for chain ID {chain_id}: {str(e)}", exc_info=True)

def main():
    setup_logging()  # Configure logging before anything else
    # Load environment variables (still needed for API keys, etc.)
    load_dotenv()

    supported_chain_ids_str = os.getenv("SUPPORTED_CHAIN_IDS")
    if not supported_chain_ids_str:
        logger.error("SUPPORTED_CHAIN_IDS environment variable not set. Should be comma-separated (e.g., 8453,137).")
        return

    supported_chain_ids = []
    try:
        supported_chain_ids = [int(cid.strip()) for cid in supported_chain_ids_str.split(',')]
    except ValueError:
        logger.error("Invalid format for SUPPORTED_CHAIN_IDS. Should be comma-separated integers.")
        return

    # Define allowed chains here or import from config if preferred
    allowed_chains = {8453, 137}
    valid_chain_ids = [cid for cid in supported_chain_ids if cid in allowed_chains]
    invalid_chain_ids = [cid for cid in supported_chain_ids if cid not in allowed_chains]

    if invalid_chain_ids:
        logger.warning(f"Unsupported chain IDs found in SUPPORTED_CHAIN_IDS and will be ignored: {invalid_chain_ids}. Supported: {allowed_chains}")

    if not valid_chain_ids:
        logger.error("No valid/supported chain IDs found in SUPPORTED_CHAIN_IDS.")
        return

    logger.info(f"Starting automation runs for networks: {valid_chain_ids}")

    async def run_all():
        tasks = [run_automation_for_network(chain_id) for chain_id in valid_chain_ids]
        await asyncio.gather(*tasks)

    asyncio.run(run_all())

    logger.info("All automation runs completed.")

if __name__ == "__main__":
    main()
