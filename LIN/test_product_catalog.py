import unittest

from product_catalog import DEFAULT_PRODUCT_CODE, get_product_definition, list_known_products, list_runtime_supported_products


class ProductCatalogTests(unittest.TestCase):
    def test_default_product_is_a045(self):
        self.assertEqual(DEFAULT_PRODUCT_CODE, "A045")

    def test_a050_is_registered_with_protocol_metadata(self):
        product = get_product_definition("A050")

        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(product.command_pid, 0x36)
        self.assertEqual(product.status_pid, 0x37)
        self.assertEqual(product.aux_status_pid, 0x39)
        self.assertTrue(product.runtime_supported)

    def test_runtime_supported_products_remain_safe_subset(self):
        runtime_codes = [product.code for product in list_runtime_supported_products()]
        known_codes = [product.code for product in list_known_products()]

        self.assertIn("A045", runtime_codes)
        self.assertIn("A050", known_codes)
        self.assertIn("A050", runtime_codes)


if __name__ == "__main__":
    unittest.main()
