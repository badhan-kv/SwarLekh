import single_instance


def test_second_acquire_of_same_name_is_refused():
    name = "Local\\SwarLekh-test-mutex-1"
    assert single_instance.acquire(name) is True
    assert single_instance.acquire(name) is False


def test_different_names_do_not_conflict():
    assert single_instance.acquire("Local\\SwarLekh-test-mutex-2") is True
    assert single_instance.acquire("Local\\SwarLekh-test-mutex-3") is True
