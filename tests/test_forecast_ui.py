import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

class ForecastUITests(unittest.TestCase):
    def test_manual_run_and_stale_results(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
        self.assertEqual(len(app.exception),0)
        app.segmented_control[0].set_value('Forecast').run()
        self.assertEqual(len(app.exception),0)
        self.assertNotIn('forecast_result',app.session_state)
        next(x for x in app.button if x.label=='Run House forecast').click().run(timeout=60)
        self.assertEqual(len(app.exception),0)
        self.assertIn('forecast_result',app.session_state)
        app.number_input[0].set_value(35.).run()
        self.assertNotIn('forecast_result',app.session_state)
        self.assertEqual(len(app.exception),0)
