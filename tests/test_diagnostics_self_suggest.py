"""B2 regression: 'Did you mean X?' must never suggest the exact token typed."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.errors import _did_you_mean


class TestDidYouMeanSelfSuggest(unittest.TestCase):
    def test_helper_never_suggests_the_input_itself(self):
        # Previously this produced "Did you mean: End?" for the word "End".
        msg = _did_you_mean('End', ['End', 'And', 'Send'])
        self.assertNotIn('End?', msg)
        # A genuinely different candidate is still offered.
        self.assertTrue('And' in msg or 'Send' in msg)

    def test_helper_is_case_insensitive_about_self(self):
        msg = _did_you_mean('page', ['Page', 'Stage'])
        self.assertNotIn('Page?', msg)

    def test_helper_returns_empty_when_only_self_matches(self):
        self.assertEqual(_did_you_mean('Route', ['Route']), '')


if __name__ == '__main__':
    unittest.main()
