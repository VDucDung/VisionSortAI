import unittest
from trashsmart.yolo_training.search_accuracy import choose_operating_point, operating_metrics, stable_threshold
from trashsmart.yolo_training.train_accuracy import balanced_score


class OperatingPointTests(unittest.TestCase):
    def test_stable_threshold_avoids_including_a_boundary_prediction_differently(self):
        scores = [.9, .8, .7, .2]
        threshold = stable_threshold(scores, .8)
        self.assertGreater(threshold, .7)
        self.assertLess(threshold, .8)
        self.assertEqual([score for score in scores if score > threshold], [.9, .8])

    def test_balanced_training_selection_does_not_reward_high_map_and_poor_recall(self):
        self.assertGreater(balanced_score(.91, .89), balanced_score(.96, .8))
        with self.assertRaises(ValueError):
            balanced_score(float("nan"), .9)

    def test_lower_threshold_changes_recall_with_precision_accounted_for(self):
        scores, tp = [.9, .8, .7, .2], [1, 1, 0, 1]
        point = choose_operating_point(scores, tp, 3, target_recall=1, min_precision=.75)
        self.assertTrue(point["target_met"])
        self.assertEqual(point["point"]["confidence"], .2)
        self.assertEqual(point["point"]["precision"], .75)
        self.assertEqual(operating_metrics(scores, tp, 3, .35)["recall"], 2/3)

    def test_precision_floor_prevents_trivial_recall_claim(self):
        point = choose_operating_point([.9, .8, .7, .2], [1, 1, 0, 1], 3, 1, .8)
        self.assertFalse(point["target_met"])
        self.assertEqual(point["point"]["recall"], 2/3)

    def test_tied_scores_are_all_included(self):
        point = choose_operating_point([.9, .8, .8], [1, 1, 0], 2, 1, .8)
        self.assertFalse(point["target_met"])
        self.assertEqual(point["point"]["confidence"], .9)

    def test_empty_predictions_do_not_satisfy_target(self):
        self.assertEqual(choose_operating_point([], [], 10), dict(target_met=False, point=None))

    def test_unannotated_validation_is_rejected(self):
        with self.assertRaises(ValueError):
            choose_operating_point([], [], 0)


if __name__ == "__main__":
    unittest.main()
