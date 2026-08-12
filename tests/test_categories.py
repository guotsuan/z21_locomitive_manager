import unittest

from src.categories import (
    CategoryValidationError,
    normalize_category,
    parse_categories,
)


class CategoryRulesTests(unittest.TestCase):
    def test_standard_categories_are_case_insensitively_canonicalized(self):
        self.assertEqual(normalize_category("diesel"), "Diesel")
        self.assertEqual(normalize_category("TRAIN   BUS"), "Train Bus")
        self.assertEqual(normalize_category("electrical"), "Electrical")

    def test_custom_category_must_be_short_english_title_case(self):
        self.assertEqual(normalize_category("Battery Electric"),
                         "Battery Electric")
        with self.assertRaises(CategoryValidationError):
            normalize_category("battery electric")
        with self.assertRaises(CategoryValidationError):
            normalize_category("任意类型")

    def test_categories_are_deduplicated(self):
        self.assertEqual(parse_categories("Diesel, diesel, Heritage Train"),
                         ("Diesel", "Heritage Train"))


if __name__ == "__main__":
    unittest.main()
