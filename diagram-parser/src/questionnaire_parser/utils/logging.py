import logging
import os
from pathlib import Path

def setup_logger(name: str) -> logging.Logger:
    """
    Set up and configure logger with both file and console handlers.
    
    Args:
        name: Name of the logger, typically __name__ from the calling module
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING)

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create file handler
    fh = logging.FileHandler(log_dir / "parser.log")
    fh.setLevel(logging.WARNING)

    # Create console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Add handlers to logger if they haven't been added already
    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger