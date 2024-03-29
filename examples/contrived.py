"""
This is a stubbed pipeline that does 4 steps in sequence.
All the steps are mocked and they will just pass through.
Use this pattern to define the skeleton of your pipeline and flesh out the steps later.

You can run this pipeline by python run examples/contrived.py
"""

from magnus import Pipeline, Stub


def main():
    acquire_data = Stub(name="Acquire Data", next="Prepare Data")  # (1)

    prepare_data = Stub(name="Prepare Data")

    extract_features = Stub(name="Extract Features").depends_on(prepare_data)

    modelling = Stub(name="Model", terminate_with_success=True)  # (2)

    extract_features >> modelling  # (3)

    pipeline = Pipeline(
        steps=[acquire_data, prepare_data, extract_features, modelling],
        start_at=acquire_data,
        add_terminal_nodes=True,
    )  # (4)

    run_log = pipeline.execute()  # (5)
    print(run_log)


if __name__ == "__main__":
    main()
