"""Destination discovery must consider all API pages before selection."""

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[1] / "canonical/tools/deploy_connector.py"


class DestinationPaginationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("destination_fixture", HELPER)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)

    def discover(self, pages, selection="2"):
        requests = []

        def get(path, key):
            self.assertEqual(key, "fixture-key")
            requests.append(path)
            return pages[len(requests) - 1]

        with patch.object(self.helper, "fivetran_get", get), \
             patch("builtins.input", return_value=selection), \
             contextlib.redirect_stdout(io.StringIO()):
            name = self.helper.discover_destination_name("fixture-key")
        return name, requests

    def test_selects_destination_on_later_page(self):
        name, requests = self.discover([
            {"data": {"items": [{"id": "first", "name": "First"}], "next_cursor": "next"}},
            {"data": {"items": [{"id": "second", "name": "Second"}]}},
        ])
        self.assertEqual(name, "Second")
        self.assertEqual(requests, ["/groups?limit=1000", "/groups?limit=1000&cursor=next"])

    def test_empty_page_with_cursor_is_not_an_empty_account(self):
        name, requests = self.discover([
            {"data": {"items": [], "next_cursor": "next"}},
            {"data": {"items": [{"id": "second", "name": "Second"}]}},
        ])
        self.assertEqual(name, "Second")
        self.assertEqual(len(requests), 2)

    def test_cursor_is_encoded_as_one_query_parameter(self):
        name, requests = self.discover([
            {"data": {"items": [{"id": "first", "name": "First"}], "next_cursor": "a+/=& b"}},
            {"data": {"items": [{"id": "second", "name": "Second"}]}},
        ])
        self.assertEqual(name, "Second")
        self.assertEqual(requests[-1], "/groups?limit=1000&cursor=a%2B%2F%3D%26+b")

    def test_single_destination_still_auto_selects(self):
        name, requests = self.discover([
            {"data": {"items": [{"id": "only", "name": "Only"}]}}
        ])
        self.assertEqual(name, "Only")
        self.assertEqual(requests, ["/groups?limit=1000"])

    def test_empty_account_still_exits(self):
        with self.assertRaises(SystemExit) as error:
            self.discover([{"data": {"items": []}}])
        self.assertEqual(error.exception.code, 1)
