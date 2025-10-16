"""
Crawler Service Entry Point

Main entry point for the crawler service.
"""

import logging
import sys
import argparse
from pathlib import Path

from src.core.logger import setup_logging, suppress_noisy_loggers
from src.config.config import load_config
from src.workers.controller import CrawlerController


def parse_args():
    """Parse command line arguments

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Universal Crawler Service - Configurable data crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py                          # Use default config
  python src/main.py -c custom_config.yaml    # Use custom config
  python src/main.py --log-level DEBUG        # Set log level to DEBUG
        """
    )

    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Config file path (default: config.yaml)"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override config file log level"
    )

    parser.add_argument(
        "--no-redis",
        action="store_true",
        help="Disable Redis tracking (use database only)"
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse arguments
    args = parse_args()

    try:
        # Load config
        print(f"Loading config from: {args.config}")
        config = load_config(args.config)

        # Setup logging
        log_config = config.get("logging", {})
        log_level = args.log_level or log_config.get("level", "INFO")
        log_file = log_config.get("file", "./logs/crawler.log")
        max_bytes = log_config.get("max_bytes", 5242880)
        backup_count = log_config.get("backup_count", 5)

        setup_logging(
            log_level=log_level,
            log_file=log_file,
            max_bytes=max_bytes,
            backup_count=backup_count,
            console_output=True,
        )

        # Suppress noisy third-party loggers
        suppress_noisy_loggers()

        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("Crawler Service Starting")
        logger.info("=" * 60)
        logger.info(f"Config: {args.config}")
        logger.info(f"Log Level: {log_level}")
        logger.info(f"Log File: {log_file}")

        # Handle --no-redis flag
        if args.no_redis:
            logger.warning("Redis tracking disabled")
            config["redis"] = {"url": None}

        # Initialize controller
        controller = CrawlerController(config)

        # Run all enabled sources
        all_stats = controller.run_all()

        # Check for errors
        total_errors = sum(s.errors for s in all_stats.values())
        if total_errors > 0:
            logger.warning(f"Completed with {total_errors} errors")
            sys.exit(1)

        logger.info("All tasks completed successfully")
        sys.exit(0)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
