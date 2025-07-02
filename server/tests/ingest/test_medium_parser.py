import os
from superdesk.errors import ParserError
from pesacheck.ingest.medium_parser import MediumParser

from .. import BaseTestCase


class MediumParserTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()

        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture_path = os.path.normpath(os.path.join(dirname, "../fixtures/medium_export"))
        self.file_path = os.path.join(
            fixture_path,
            "2022-02-27_HOAX--This-UNAIDS-job-advert-in-Uganda-is-fake-f8d269a3d85d.html",
        )
        self.parser = MediumParser()

    def test_can_parse(self):
        self.assertTrue(self.parser.can_parse(self.file_path))
        self.assertFalse(self.parser.can_parse(__file__))

    def test_parse_medium_html(self):
        item = self.parser.parse(self.file_path)

        self.assertEqual(item["headline"], "HOAX: This UNAIDS job advert in Uganda is fake")
        self.assertEqual(
            item["abstract"], "A UNAIDS Communications officer told PesaCheck that the job advertisement is fake."
        )
        self.assertTrue(item["body_html"].startswith("<section"))
        self.assertEqual(item["firstcreated"].isoformat(), "2022-02-27T07:26:36.217000")
        self.assertEqual(item["byline"], "PesaCheck")
        self.assertEqual(item["source"], "Medium")

    def test_parse_invalid_html(self):
        with self.assertRaises(ParserError) as cm:
            self.parser.parse("invalid_file_path")
        self.assertEqual(cm.exception.code, 1002)

    def test_parse_html_without_article(self):
        with open("test_file.html", "w") as f:
            f.write("<html><body>No article here</body></html>")
        try:
            with self.assertRaises(ParserError) as cm:
                self.parser.parse("test_file.html")
            self.assertEqual(cm.exception.code, 1002)
        finally:
            os.remove("test_file.html")
