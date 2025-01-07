import logging
import os
import colorlog
from typing import Optional

class PaddedModuleFormatter(colorlog.ColoredFormatter):
    """Custom formatter that pads module names to a fixed width"""
    def __init__(self, *args, module_width: int = 25, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_width = module_width

    def format(self, record):
        # Shorten the module name if it's too long
        if len(record.name) > self.module_width:
            record.name = "..." + record.name[-(self.module_width-3):]
        else:
            # Pad with spaces if it's shorter
            record.name = record.name.ljust(self.module_width)
        
        return super().format(record)

def setup_logging(level: Optional[str] = None):
    """Configure logging for the application with colors and fixed-width module names"""
    # Get log level from environment or use default
    log_level = level or os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Create console handler
    console_handler = colorlog.StreamHandler()
    
    # Create formatter
    formatter = PaddedModuleFormatter(
        '%(asctime)s %(blue)s%(name)s%(reset)s %(log_color)s%(levelname)-8s%(reset)s %(message)s',
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%',
        module_width=25
    )
    
    # Add formatter to handler
    console_handler.setFormatter(formatter)
    
    # Get root logger and set level
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers and add our custom handler
    root_logger.handlers = []
    root_logger.addHandler(console_handler)
    
    # Disable noisy loggers
    logging.getLogger('gql.transport.aiohttp').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.client').setLevel(logging.WARNING)
    logging.getLogger('web3.providers').setLevel(logging.WARNING)
    logging.getLogger('web3.requestmanager').setLevel(logging.WARNING)
