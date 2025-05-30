#!/usr/bin/env python3
"""
Migration script to convert old data format to simplified storage format
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add the src directory to Python path
sys.path.insert(0, "src")

from car_scraper.storage.simplified_listings import SimplifiedListingsStorage
from car_scraper.utils.logger import logger


def migrate_model_data(data_dir: Path, model: str, dry_run: bool = True) -> bool:
    """
    Migrate a single model from old format to simplified format

    Args:
        data_dir: Base data directory
        model: Model name to migrate
        dry_run: If True, show what would be done without actually doing it

    Returns:
        True if migration was successful
    """
    model_dir = data_dir / model
    if not model_dir.exists():
        print(f"❌ Model directory {model_dir} does not exist")
        return False

    # Check for old format files
    csv_file = model_dir / f"{model}.csv"
    json_file = model_dir / f"{model}.json"
    history_file = model_dir / "listings_history.json"
    individual_dir = model_dir / "individual_listings"

    old_files = []
    if csv_file.exists():
        old_files.append(csv_file)
    if json_file.exists():
        old_files.append(json_file)
    if history_file.exists():
        old_files.append(history_file)
    if individual_dir.exists():
        old_files.append(individual_dir)

    if not old_files:
        print(f"✅ {model}: Already in simplified format or no data found")
        return True

    print(f"\n📁 Migrating {model}...")
    print(f"   Found old format files: {[f.name for f in old_files]}")

    try:
        # Use SimplifiedListingsStorage to read the old data
        storage = SimplifiedListingsStorage(str(data_dir))
        df = storage.get_historical_data(model)

        if len(df) == 0:
            print(f"⚠️  {model}: No data found to migrate")
            return True

        print(f"   📊 Found {len(df)} historical records")

        # Check if simplified format already exists
        simplified_file = model_dir / f"{model}.json"
        if simplified_file.exists():
            try:
                with open(simplified_file, "r") as f:
                    data = json.load(f)
                if "metadata" in data and "listings" in data:
                    print(f"   ✅ Simplified format already exists")
                    if not dry_run:
                        # Backup old files
                        backup_dir = (
                            data_dir
                            / f"backup_old_format_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            / model
                        )
                        backup_dir.mkdir(parents=True, exist_ok=True)

                        for old_file in old_files:
                            if (
                                old_file != simplified_file
                            ):  # Don't backup the new format file
                                if old_file.is_dir():
                                    shutil.copytree(
                                        old_file,
                                        backup_dir / old_file.name,
                                        dirs_exist_ok=True,
                                    )
                                else:
                                    shutil.copy2(old_file, backup_dir / old_file.name)

                        print(f"   💾 Backed up old files to {backup_dir}")

                        # Remove old files
                        for old_file in old_files:
                            if (
                                old_file != simplified_file
                            ):  # Don't remove the new format file
                                if old_file.is_dir():
                                    shutil.rmtree(old_file)
                                else:
                                    old_file.unlink()

                        print(f"   🗑️  Removed old format files")
                    return True
            except Exception:
                pass  # File exists but not in new format, continue with migration

        if dry_run:
            print(f"   🔄 Would convert to simplified format")
            print(f"   💾 Would backup old files")
            print(f"   🗑️  Would remove old format files")
        else:
            # Group data by listing ID and create price history
            listings_data = {}

            # Sort by timestamp to ensure chronological order
            df_sorted = df.sort_values("scrape_timestamp")

            for _, row in df_sorted.iterrows():
                listing_id = row["id"]

                if listing_id not in listings_data:
                    listings_data[listing_id] = {
                        "id": listing_id,
                        "title": row["title"],
                        "current_price": row["price"],
                        "year": row["year"],
                        "mileage": row.get("mileage"),
                        "url": row["url"],
                        "model": row["model"],
                        "first_seen": row["date"],
                        "last_seen": row["date"],
                        "price_readings": [],
                    }

                # Update current price and last seen date
                listings_data[listing_id]["current_price"] = row["price"]
                listings_data[listing_id]["last_seen"] = row["date"]

                # Add price reading
                listings_data[listing_id]["price_readings"].append(
                    {
                        "price": row["price"],
                        "date": row["date"],
                        "timestamp": int(row["scrape_timestamp"]),
                    }
                )

            # Create the new format structure
            new_data = {
                "metadata": {
                    "model": model,
                    "last_updated": datetime.now().isoformat(),
                    "total_listings": len(listings_data),
                    "total_price_readings": sum(
                        len(listing["price_readings"])
                        for listing in listings_data.values()
                    ),
                },
                "listings": listings_data,
            }

            # Backup old files first
            backup_dir = (
                data_dir
                / f"backup_old_format_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                / model
            )
            backup_dir.mkdir(parents=True, exist_ok=True)

            for old_file in old_files:
                if old_file.is_dir():
                    shutil.copytree(
                        old_file, backup_dir / old_file.name, dirs_exist_ok=True
                    )
                else:
                    shutil.copy2(old_file, backup_dir / old_file.name)

            print(f"   💾 Backed up old files to {backup_dir}")

            # Write new format
            with open(simplified_file, "w", encoding="utf-8") as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)

            print(f"   ✅ Created simplified format with {len(listings_data)} listings")

            # Remove old files (except the new one)
            for old_file in old_files:
                if old_file != simplified_file:  # Don't remove the new format file
                    if old_file.is_dir():
                        shutil.rmtree(old_file)
                    else:
                        old_file.unlink()

            print(f"   🗑️  Removed old format files")

        return True

    except Exception as e:
        print(f"❌ Error migrating {model}: {e}")
        logger.error(f"Migration error for {model}: {e}")
        return False


def main():
    """Main migration function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate old data format to simplified storage"
    )
    parser.add_argument("--data-dir", default="./data", help="Data directory path")
    parser.add_argument("--model", help="Specific model to migrate (optional)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be done without actually doing it",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the migration (overrides --dry-run)",
    )

    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"❌ Data directory {data_dir} does not exist")
        return 1

    print("🚀 Car Scraper Data Migration Tool")
    print("=" * 50)
    print(f"📁 Data directory: {data_dir}")
    print(f"🔄 Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")

    if args.dry_run:
        print("\n⚠️  This is a DRY RUN. Use --execute to actually perform migration.")

    # Find models to migrate
    models_to_migrate = []
    if args.model:
        models_to_migrate = [args.model]
    else:
        # Find all model directories
        for item in data_dir.iterdir():
            if (
                item.is_dir()
                and not item.name.startswith(".")
                and not item.name.startswith("backup")
            ):
                models_to_migrate.append(item.name)

    if not models_to_migrate:
        print("❌ No models found to migrate")
        return 1

    print(f"\n📊 Found {len(models_to_migrate)} models to migrate: {models_to_migrate}")

    # Migrate each model
    success_count = 0
    for model in models_to_migrate:
        if migrate_model_data(data_dir, model, args.dry_run):
            success_count += 1

    print(f"\n{'=' * 50}")
    print(
        f"✅ Migration completed: {success_count}/{len(models_to_migrate)} models successful"
    )

    if args.dry_run:
        print("\n💡 To actually perform the migration, run with --execute flag")
    else:
        print("\n🎉 Migration completed successfully!")
        print("📋 Old format files have been backed up and can be safely removed later")

    return 0 if success_count == len(models_to_migrate) else 1


if __name__ == "__main__":
    sys.exit(main())
