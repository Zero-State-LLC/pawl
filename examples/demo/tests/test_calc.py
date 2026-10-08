from calc import add, mean, subtract


def test_add():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-2, -3) == -5


def test_subtract():
    assert subtract(5, 3) == 2


def test_mean():
    assert mean([1.0, 2.0, 3.0]) == 2.0


def test_mean_empty():
    # Known debt: the docstring promises 0.0 for an empty list.
    assert mean([]) == 0.0
