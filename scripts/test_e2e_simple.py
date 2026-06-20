#!/usr/bin/env python3
"""
Simple e2e test for the simplified storage system.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.car_scraper.plotters import IndividualListingsPlotter, YearAnalysisPlotter
from src.car_scraper.storage import SimplifiedListingsStorage
from src.car_scraper.utils import DataProcessor


def test_complete_workflow():
    """Test the complete workflow from storage to plotting."""
    print("🚀 Starting E2E Test for Simplified Storage System")

    # Create temporary test directory
    test_dir = Path(tempfile.mkdtemp())
    test_data_dir = test_dir / "data"
    test_data_dir.mkdir()

    try:
        # Test model and sample data
        test_model = "test-bmw-320i"
        sample_listings = [
            {
                "id": "car-1-abc123.html",
                "title": "BMW 320i 2020",
                "price": 150000,
                "year": 2020,
                "mileage": 45000,
                "url": "https://example.com/car-1.html",
                "model": test_model,
                "scrape_date": "2025-05-31",
                "scrape_timestamp": 1748640000,
            },
            {
                "id": "car-2-def456.html",
                "title": "BMW 320i 2021",
                "price": 180000,
                "year": 2021,
                "mileage": 25000,
                "url": "https://example.com/car-2.html",
                "model": test_model,
                "scrape_date": "2025-05-31",
                "scrape_timestamp": 1748640001,
            },
            {
                "id": "car-3-ghi789.html",
                "title": "BMW 320i 2022",
                "price": 200000,
                "year": 2022,
                "mileage": 15000,
                "url": "https://example.com/car-3.html",
                "model": test_model,
                "scrape_date": "2025-05-31",
                "scrape_timestamp": 1748640002,
            },
        ]

        print("\n📊 Step 1: Testing Data Storage")

        # Test 1: Create storage and store data
        storage = SimplifiedListingsStorage(str(test_data_dir))
        storage.store_listings_data(test_model, sample_listings, "2025-05-31")

        # Verify file structure
        data_file = test_data_dir / test_model / f"{test_model}.json"
        assert data_file.exists(), "❌ Data file was not created"

        with open(data_file) as f:
            data = json.load(f)

        assert "metadata" in data, "❌ Missing metadata section"
        assert "listings" in data, "❌ Missing listings section"
        assert (
            len(data["listings"]) == 3
        ), f"❌ Expected 3 listings, got {len(data['listings'])}"
        print("✅ Data storage test passed")

        print("\n📈 Step 2: Testing Data Retrieval")

        # Test 2: Retrieve and verify data
        df = storage.get_historical_data(test_model)
        assert len(df) == 3, f"❌ Expected 3 rows, got {len(df)}"
        assert "price" in df.columns, "❌ Missing price column"
        assert all(df["price"] > 0), "❌ Invalid prices found"
        print("✅ Data retrieval test passed")

        print("\n🔄 Step 3: Testing Price Change Tracking")

        # Test 3: Test price changes
        updated_listings = [
            {
                "id": "car-1-abc123.html",
                "title": "BMW 320i 2020",
                "price": 145000,  # Price decreased
                "year": 2020,
                "mileage": 45000,
                "url": "https://example.com/car-1.html",
                "model": test_model,
                "scrape_date": "2025-06-01",
                "scrape_timestamp": 1748726400,
            },
            {
                "id": "car-2-def456.html",
                "title": "BMW 320i 2021",
                "price": 185000,  # Price increased
                "year": 2021,
                "mileage": 25000,
                "url": "https://example.com/car-2.html",
                "model": test_model,
                "scrape_date": "2025-06-01",
                "scrape_timestamp": 1748726401,
            },
        ]

        storage.store_listings_data(test_model, updated_listings, "2025-06-01")

        # Verify price changes
        with open(data_file) as f:
            updated_data = json.load(f)

        car1 = updated_data["listings"]["car-1-abc123.html"]
        assert car1["current_price"] == 145000, "❌ Price change not tracked correctly"
        assert car1["price_change"] == -5000, "❌ Price change calculation incorrect"
        assert len(car1["price_readings"]) == 2, "❌ Price history not maintained"
        print("✅ Price change tracking test passed")

        print("\n📊 Step 4: Testing Individual Plots")

        # Test 4: Generate individual plots
        individual_plotter = IndividualListingsPlotter(str(test_data_dir))
        individual_plotter.generate_individual_listing_plots(test_model)

        plots_dir = test_dir / "plots" / test_model
        individual_plot = plots_dir / "individual_listings_trends.png"
        assert individual_plot.exists(), "❌ Individual plot was not created"
        print("✅ Individual plots test passed")

        print("\n📈 Step 5: Testing Year Analysis Plots")

        # Test 5: Generate year analysis plots
        year_plotter = YearAnalysisPlotter(str(test_data_dir))
        year_plotter.generate_year_analysis_plots(test_model)

        expected_plots = [
            "year_analysis.png",
            "listings_by_year.png",
            "price_vs_mileage.png",
        ]
        for plot_name in expected_plots:
            plot_file = plots_dir / plot_name
            assert plot_file.exists(), f"❌ {plot_name} was not created"
        print("✅ Year analysis plots test passed")

        print("\n🔧 Step 6: Testing Data Processor")

        # Test 6: Data processor functionality
        processor = DataProcessor(str(test_data_dir))
        status = processor.get_data_status()

        assert (
            "simplified_listings" in status
        ), "❌ DataProcessor not detecting simplified listings"
        assert (
            test_model in status["simplified_listings"]
        ), "❌ Test model not found in status"

        model_status = status["simplified_listings"][test_model]
        assert (
            model_status["total_listings"] == 3
        ), f"❌ Wrong listing count: {model_status['total_listings']}"
        assert model_status["total_price_readings"] > 3, "❌ Price readings not tracked"
        print("✅ Data processor test passed")

        print("\n🔍 Step 7: Testing Backward Compatibility")

        # Test 7: Backward compatibility with old format
        old_model = "old-format-test"
        old_data = [
            {
                "id": "old-car-1.html",
                "title": "Old Format Car",
                "price": 100000,
                "year": 2019,
                "mileage": 50000,
                "url": "https://example.com/old-car.html",
                "model": old_model,
                "scrape_date": "2025-05-30T10:00:00",
                "scrape_timestamp": 1748550000,
            }
        ]

        # Create old format file
        old_model_dir = test_data_dir / old_model
        old_model_dir.mkdir()
        old_data_file = old_model_dir / f"{old_model}.json"

        with open(old_data_file, "w") as f:
            json.dump(old_data, f, indent=2)

        # Test reading old format
        df_old = storage.get_historical_data(old_model)
        assert len(df_old) == 1, "❌ Failed to read old format data"
        assert (
            df_old["price"].iloc[0] == 100000
        ), "❌ Old format price not read correctly"
        print("✅ Backward compatibility test passed")

        print("\n🎉 ALL TESTS PASSED!")
        print("✅ SimplifiedListingsStorage system is working correctly")
        print("✅ All core functionality is intact")
        print("✅ Backward compatibility is maintained")
        print("✅ Plotting system integration works")
        print("✅ Data processing functionality works")
        print("✅ Price change tracking is operational")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        shutil.rmtree(test_dir)
        print(f"\n🧹 Cleaned up test directory: {test_dir}")


if __name__ == "__main__":
    success = test_complete_workflow()
    sys.exit(0 if success else 1)
