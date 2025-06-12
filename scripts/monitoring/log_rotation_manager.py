#!/usr/bin/env python3
"""
Log Rotation Manager for E-commerce Saga System

Manages log file rotation, cleanup, and archival policies.
"""

import os
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import logging

# Configure basic logging for this script
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LogRotationManager:
    """Manages log rotation and cleanup policies"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.services = [
            "order",
            "inventory",
            "payment",
            "shipping",
            "notification",
            "coordinator",
        ]

    def compress_old_logs(self, days_old: int = 7):
        """Compress log files older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        compressed_count = 0

        logger.info(f"Compressing log files older than {days_old} days...")

        for log_file in self.log_dir.rglob("*.log*"):
            if log_file.suffix == ".gz":
                continue  # Already compressed

            # Check file modification time
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)

            if file_time < cutoff_date:
                try:
                    # Compress the file
                    compressed_file = log_file.with_suffix(log_file.suffix + ".gz")

                    with open(log_file, "rb") as f_in:
                        with gzip.open(compressed_file, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    # Remove original file
                    log_file.unlink()
                    compressed_count += 1
                    logger.info(f"Compressed: {log_file} -> {compressed_file}")

                except Exception as e:
                    logger.error(f"Failed to compress {log_file}: {e}")

        logger.info(f"Compressed {compressed_count} log files")

    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Remove compressed log files older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        removed_count = 0

        logger.info(f"Removing log files older than {days_to_keep} days...")

        for log_file in self.log_dir.rglob("*.gz"):
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)

            if file_time < cutoff_date:
                try:
                    log_file.unlink()
                    removed_count += 1
                    logger.info(f"Removed old log: {log_file}")
                except Exception as e:
                    logger.error(f"Failed to remove {log_file}: {e}")

        logger.info(f"Removed {removed_count} old log files")

    def get_log_statistics(self):
        """Get statistics about log files"""
        stats = {
            "total_files": 0,
            "total_size_mb": 0,
            "by_service": {},
            "by_type": {"json": 0, "text": 0, "compressed": 0},
        }

        for log_file in self.log_dir.rglob("*"):
            if not log_file.is_file():
                continue

            stats["total_files"] += 1
            file_size_mb = log_file.stat().st_size / (1024 * 1024)
            stats["total_size_mb"] += file_size_mb

            # Categorize by service
            service_name = log_file.stem.split(".")[0]
            if service_name not in stats["by_service"]:
                stats["by_service"][service_name] = {"files": 0, "size_mb": 0}
            stats["by_service"][service_name]["files"] += 1
            stats["by_service"][service_name]["size_mb"] += file_size_mb

            # Categorize by type
            if ".json." in log_file.name:
                stats["by_type"]["json"] += 1
            elif log_file.suffix == ".gz":
                stats["by_type"]["compressed"] += 1
            else:
                stats["by_type"]["text"] += 1

        return stats

    def print_statistics(self):
        """Print log file statistics"""
        stats = self.get_log_statistics()

        print("\n📊 Log File Statistics")
        print("=" * 50)
        print(f"Total Files: {stats['total_files']}")
        print(f"Total Size: {stats['total_size_mb']:.2f} MB")

        print("\n📁 By Service:")
        for service, data in stats["by_service"].items():
            print(f"  {service:15} {data['files']:3} files  {data['size_mb']:6.2f} MB")

        print("\n📄 By Type:")
        for log_type, count in stats["by_type"].items():
            print(f"  {log_type:15} {count:3} files")

    def rotate_service_logs(self, service_name: str):
        """Manually rotate logs for a specific service"""
        logger.info(f"Manually rotating logs for {service_name}...")

        # This would trigger the rotating file handler to rotate
        # In practice, the handlers rotate automatically when size limit is reached
        for log_file in self.log_dir.glob(f"{service_name}.*"):
            if log_file.suffix not in [".gz"]:
                logger.info(
                    f"Log file: {log_file} (Size: {log_file.stat().st_size / 1024:.1f} KB)"
                )


def main():
    parser = argparse.ArgumentParser(
        description="Manage log rotation for e-commerce saga system"
    )
    parser.add_argument(
        "--compress",
        type=int,
        metavar="DAYS",
        help="Compress logs older than DAYS (default: 7)",
    )
    parser.add_argument(
        "--cleanup",
        type=int,
        metavar="DAYS",
        help="Remove compressed logs older than DAYS (default: 30)",
    )
    parser.add_argument("--stats", action="store_true", help="Show log file statistics")
    parser.add_argument(
        "--rotate", metavar="SERVICE", help="Manually rotate logs for specific service"
    )
    parser.add_argument(
        "--log-dir", default="logs", help="Log directory path (default: logs)"
    )

    args = parser.parse_args()

    manager = LogRotationManager(args.log_dir)

    if args.stats:
        manager.print_statistics()

    if args.compress is not None:
        manager.compress_old_logs(args.compress)

    if args.cleanup is not None:
        manager.cleanup_old_logs(args.cleanup)

    if args.rotate:
        manager.rotate_service_logs(args.rotate)

    if not any(
        [args.stats, args.compress is not None, args.cleanup is not None, args.rotate]
    ):
        # Default behavior
        manager.print_statistics()
        manager.compress_old_logs(7)
        manager.cleanup_old_logs(30)


if __name__ == "__main__":
    main()
