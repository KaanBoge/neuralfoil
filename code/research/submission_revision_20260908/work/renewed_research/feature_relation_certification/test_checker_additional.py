"""Root-owned synthetic min/max path-pruning checks; no model/data access."""
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'uncertainty_review/range_bound_feasibility'))
import test_relation_checker as reference


class AdditionalCheckerTests(unittest.TestCase):
    def test_minimum_path_exclusion(self):
        for first, second in [(12, 13), (13, 12)]:
            tree = np.zeros(7, dtype=reference.DT)
            for i in (1, 3, 5, 6):
                tree[i]['is_leaf'] = 1
                tree[i]['value'] = 10.0
            for index, feature, left, right in [(0, first, 1, 2), (2, second, 3, 4), (4, 18, 5, 6)]:
                tree[index]['feature_idx'] = feature
                tree[index]['num_threshold'] = 0.0
                tree[index]['left'], tree[index]['right'] = left, right
            tree[5]['value'], tree[6]['value'] = 99.0, 1.0
            model = reference.E.SequentialHist(reference.arrays([tree]), required_stages=1)
            checkpoint = reference.checkpoint()
            checkpoint['upper'] = checkpoint['frontier'][0]['upper'] = '10'
            checkpoint['frontier'][0]['cuts'] = []
            result = reference.c.replay(checkpoint, model.stages, model.initial, reference.Q.sequential_range)
            self.assertEqual((result['lower'], result['upper']), ('1', '10'))

    def test_maximum_path_exclusion(self):
        for first, second in [(12, 13), (13, 12)]:
            tree = np.zeros(7, dtype=reference.DT)
            for i in (2, 4, 5, 6):
                tree[i]['is_leaf'] = 1
                tree[i]['value'] = 10.0
            for index, feature, left, right in [(0, first, 1, 2), (1, second, 3, 4), (3, 19, 5, 6)]:
                tree[index]['feature_idx'] = feature
                tree[index]['num_threshold'] = 0.0
                tree[index]['left'], tree[index]['right'] = left, right
            tree[5]['value'], tree[6]['value'] = 1.0, 99.0
            model = reference.E.SequentialHist(reference.arrays([tree]), required_stages=1)
            checkpoint = reference.checkpoint()
            checkpoint['upper'] = checkpoint['frontier'][0]['upper'] = '10'
            checkpoint['frontier'][0]['cuts'] = []
            result = reference.c.replay(checkpoint, model.stages, model.initial, reference.Q.sequential_range)
            self.assertEqual((result['lower'], result['upper']), ('1', '10'))


if __name__ == '__main__':
    unittest.main()
