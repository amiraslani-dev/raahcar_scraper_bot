"""
Unit & Smoke tests for Raahcar Scraper Bot.
Ensures modules load, configurations validate, assets exist,
and vision processing runs smoothly without relying on live external networks.
"""
import os
import sys
import unittest
import numpy as np
from PIL import Image

# Ensure scraper_bot root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if SCRAPER_ROOT not in sys.path:
    sys.path.insert(0, SCRAPER_ROOT)


class TestScraperBotIntegrity(unittest.TestCase):
    def test_01_config_and_paths(self):
        """Verify configuration constants and directories exist or can be created."""
        import config
        self.assertTrue(hasattr(config, "MAIN_SERVER_URL"))
        self.assertTrue(hasattr(config, "INGESTION_API_KEY"))
        self.assertTrue(hasattr(config, "REDIS_URL"))
        self.assertTrue(os.path.isdir(config.ASSETS_DIR))
        self.assertTrue(os.path.isdir(config.TEMP_IMAGE_DIR))

    def test_02_critical_assets_exist(self):
        """Verify essential model weights and branding logos are in place."""
        import config
        critical_assets = [
            os.path.join(config.ASSETS_DIR, "logo.png"),
            os.path.join(config.ASSETS_DIR, "plate_detector.onnx"),
            os.path.join(config.ASSETS_DIR, "plate_yolo_iran.onnx"),
            os.path.join(config.ASSETS_DIR, "cars_best_v26.pt"),
            os.path.join(config.BASE_DIR, "logo.webp"),
        ]
        for asset_path in critical_assets:
            self.assertTrue(
                os.path.exists(asset_path),
                f"Missing critical asset: {os.path.basename(asset_path)}"
            )

    def test_03_module_imports(self):
        """Ensure all primary submodules import without syntax or circular import errors."""
        try:
            import config
            import scraper
            import image_processor
            import publisher
            import celery_app
            import tasks
        except Exception as e:
            self.fail(f"Module import failed: {e}")

    def test_04_image_processor_synthetic(self):
        """Verify the vision processing pipeline runs end-to-end on a synthetic test image."""
        import tempfile
        from image_processor import process_image_file

        # Generate a synthetic 400x300 RGB test image
        img_array = np.full((300, 400, 3), 180, dtype=np.uint8)
        # Draw a simulated license plate region
        img_array[180:220, 150:250] = [255, 255, 255]
        test_img = Image.fromarray(img_array)

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = os.path.join(tmp_dir, "input.jpg")
            output_path = os.path.join(tmp_dir, "output.webp")
            test_img.save(input_path, format="JPEG")

            success = process_image_file(input_path, output_path)
            self.assertTrue(success, "Image processing should return True")
            self.assertTrue(os.path.exists(output_path), "Processed output image must exist")
            self.assertGreater(os.path.getsize(output_path), 0, "Output image must not be empty")


if __name__ == "__main__":
    unittest.main()

