import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from untis_ical import parse_rest, parse_legacy, make_ics, esc, fold

class ConverterTests(unittest.TestCase):
    def test_rest_with_cancellation_and_substitution(self):
        response = {"days": [{"gridEntries": [
            {"ids": [42], "status": "SUBSTITUTION", "duration": {"start": "2026-11-18T08:00", "end": "2026-11-18T08:45"},
             "position1": [{"current": {"type": "SUBJECT", "shortName": "De"}}],
             "position2": [{"current": {"type": "ROOM", "shortName": "B12"}}],
             "position3": [{"current": {"type": "TEACHER", "shortName": "Mü"}}],
             "substitutionText": "Vertretung"},
            {"ids": [43], "status": "CANCEL", "duration": {"start": "2026-11-18T08:50", "end": "2026-11-18T09:35"},
             "position1": [{"current": {"type": "SUBJECT", "shortName": "Ma"}}]},
        ]}]}
        result = parse_rest(response)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].subject, "De")
        self.assertEqual(result[0].room, "B12")
        self.assertTrue(result[0].changed)
        self.assertTrue(result[1].cancelled)
        ics = make_ics(result, clock=datetime(2026, 11, 17, tzinfo=timezone.utc))
        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertIn("SUMMARY:Entfällt: Ma", ics)
        self.assertIn("DTSTART:20261118T070000Z", ics)
        self.assertEqual(ics.count("BEGIN:VEVENT"), 2)
        self.assertIn("TRANSP:TRANSPARENT", ics)

    def test_legacy_with_names(self):
        response = {"data": {"result": {"data": {
            "elements": [{"type": 3, "id": 15, "name": "Eng"}, {"type": 4, "id": 19, "name": "C20"}],
            "elementPeriods": {"8279": [{"id": 100, "date": 20261119, "startTime": 1015, "endTime": 1100,
               "elements": [{"type": 3, "id": 15}, {"type": 4, "id": 19}], "cellState": "STANDARD"}]}
        }}}}
        result = parse_legacy(response)
        self.assertEqual(result[0].subject, "Eng")
        self.assertEqual(result[0].room, "C20")

    def test_ics_escape_utf8_fold(self):
        self.assertEqual(esc("A, B; C\\D\nZ"), "A\\, B\\; C\\\\D\\nZ")
        for line in fold("DESCRIPTION:" + "Ä" * 150):
            self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_reject_invalid_rest(self):
        with self.assertRaises(Exception):
            parse_rest({"error": "permission denied"})

if __name__ == "__main__":
    unittest.main()
