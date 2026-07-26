from datetime import datetime, timedelta, timezone

from app.research.validation import (ResearchExample, ablations, chronological_split,
                                     dataset_hash, walk_forward)


def examples(count=10):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [ResearchExample(f"ep_{index}", start + timedelta(days=index), index % 2 == 0,
                            {"smt": index % 3 == 0, "htf_bias": index % 2 == 0})
            for index in range(count)]


def test_chronological_split_hash_walk_forward_and_ablations_are_reproducible():
    rows = examples()
    split = chronological_split(list(reversed(rows)))
    assert [len(split[name]) for name in ("development", "validation", "untouched_test")] == [6, 2, 2]
    assert split["development"][-1].timestamp < split["validation"][0].timestamp
    assert split["validation"][-1].timestamp < split["untouched_test"][0].timestamp
    assert dataset_hash(rows) == dataset_hash(list(reversed(rows)))
    folds = walk_forward(split["development"] + split["validation"])
    assert all(item["train_end"] < item["test_start"] for item in folds)
    report = ablations(split["development"])
    assert report["smt"]["present"]["sample_size"] == 2
