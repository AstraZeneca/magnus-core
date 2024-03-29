"""
The initial parameters defined in the parameters file are:
simple: 1
inner:
  x: 10
  y: "hello"

You can execute this pipeline by: python examples/parameters.py

"""

from pydantic import BaseModel


class InnerModel(BaseModel):
    """
    Captures the "inner" part of the parameters.
    The model definition can be as nested as you want.
    """

    x: int
    y: str


class NestedModel(BaseModel):  # (1)
    """
    Captures the whole parameter space of the application.
    """

    simple: int
    inner: InnerModel


def display(simple: int, inner: InnerModel):  # (2)
    """
    The parameter "simple" and "inner" can be accessed by name.
    Magnus understands the parameter "inner" as a pydantic model from
    annotation and casts it as a pydantic model.
    """
    print(simple)
    print(inner)


def return_parameters(simple: int, inner: InnerModel) -> NestedModel:  # (3)
    """
    The parameter "simple" and "inner" can be accessed by name.
    You can redefine the parameters by returning a pydantic model.
    """
    simple = 2
    inner.x = 30
    inner.y = "world!!"

    return NestedModel(simple=simple, inner=inner)


"""
The below code is only to provide a full working example.

In the real world, you can "box magnus" in pipeline definition either in
python or yaml without cluttering your application code.
"""


def main():
    from magnus import Pipeline, Task

    display = Task(name="display", command="examples.parameters.display")
    return_parameters = Task(
        name="return_parameters",
        command="examples.parameters.return_parameters",
        terminate_with_success=True,
    )

    display >> return_parameters

    pipeline = Pipeline(
        start_at=display,
        steps=[display, return_parameters],
        add_terminal_nodes=True,
    )

    run_log = pipeline.execute(parameters_file="examples/parameters_initial.yaml")
    params = run_log.parameters

    ## Reflects the changes done by "return_parameters" function call.
    assert params["simple"] == 2
    assert params["inner"] == {"x": 30, "y": "world!!"}


if __name__ == "__main__":
    main()
