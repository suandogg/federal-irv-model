import unittest

from SRC.loaders import load_category_flow_overrides


class CategoryFlowOverrideTests(unittest.TestCase):
    def test_generated_override_input_is_inactive_by_default(self):
        self.assertEqual(load_category_flow_overrides(), {})


if __name__ == "__main__":
    unittest.main()
