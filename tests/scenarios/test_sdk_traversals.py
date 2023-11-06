from rich import print

from magnus import Stub, Pipeline, Parallel


def test_sequence():
    first = Stub(name="first", next="second")
    second = Stub(name="second", terminate_with_success=True)

    pipeline = Pipeline(steps=[first, second], start_at=first, add_terminal_nodes=True)

    run_log = pipeline.execute()

    assert len(run_log.steps) == 3


def test_parallel():
    first = Stub(name="first", next="second")
    second = Stub(name="second", next="parallel_step")

    branch_first = Stub(name="branch_first", next="branch_second")
    branch_second = Stub(name="branch_second", terminate_with_success=True)

    branch_a = Pipeline(steps=[branch_first, branch_second], start_at=branch_first, add_terminal_nodes=True)
    branch_b = Pipeline(steps=[branch_first, branch_second], start_at=branch_first, add_terminal_nodes=True)

    parallel_node = Parallel(name="parallel_step", branches={"a": branch_a, "b": branch_b}, terminate_with_success=True)

    parent_pipeline = Pipeline(steps=[first, second, parallel_node], start_at=first)
    run_log = parent_pipeline.execute()

    assert len(run_log.steps) == 4
