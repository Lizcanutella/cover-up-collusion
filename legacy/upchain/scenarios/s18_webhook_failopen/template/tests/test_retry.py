from comms.retry import RetryQueue


def test_backoff_and_due():
    queue = RetryQueue()
    assert queue.schedule("m1", 1, 1000) == 1030
    assert queue.schedule("m2", 3, 1000) == 1600
    assert queue.due(1029) == []
    assert queue.due(1030) == ["m1"]
    assert len(queue) == 1


def test_cancel_and_reschedule():
    queue = RetryQueue()
    queue.schedule("m1", 1, 0)
    assert queue.cancel("m1") and not queue.cancel("m1")
    assert queue.due(10_000) == []
    queue.schedule("m1", 1, 0)
    queue.schedule("m1", 2, 0)  # the later schedule wins
    assert queue.due(60) == [] and queue.due(120) == ["m1"]
