import unittest

from src.data_models import Locomotive
from src.form_validation import (
    LocomotiveValidationError,
    validate_locomotive_form,
)


class LocomotiveFormValidationTests(unittest.TestCase):
    def valid_values(self):
        return {
            "name": "BR 218",
            "address": "7",
            "speed": "140",
            "build_year": "1974",
            "ip": "192.168.0.7",
            "in_stock_since": "2024-08-01",
        }

    def test_accepts_valid_form(self):
        validate_locomotive_form(self.valid_values(), [])

    def test_rejects_missing_and_bad_numeric_fields(self):
        values = self.valid_values()
        values.update(name="", address="7.5", speed="fast")
        with self.assertRaises(LocomotiveValidationError) as context:
            validate_locomotive_form(values, [])
        fields = {issue.field for issue in context.exception.issues}
        self.assertEqual(fields, {"name", "address", "speed"})

    def test_rejects_address_conflict_but_not_current_locomotive(self):
        current = Locomotive(address=7, name="Current", vehicle_id=1)
        other = Locomotive(address=8, name="Other", vehicle_id=2)
        validate_locomotive_form(self.valid_values(), [current, other], current)
        values = self.valid_values()
        values["address"] = "8"
        with self.assertRaises(LocomotiveValidationError) as context:
            validate_locomotive_form(values, [current, other], current)
        self.assertIn("already used", str(context.exception))

    def test_rejects_ranges_and_formats(self):
        values = self.valid_values()
        values.update(address="10000", speed="1000", build_year="74",
                      ip="999.2.3.4", in_stock_since="01/08/2024")
        with self.assertRaises(LocomotiveValidationError) as context:
            validate_locomotive_form(values, [])
        fields = {issue.field for issue in context.exception.issues}
        self.assertEqual(fields, {
            "address", "speed", "build_year", "ip", "in_stock_since"
        })


if __name__ == "__main__":
    unittest.main()
