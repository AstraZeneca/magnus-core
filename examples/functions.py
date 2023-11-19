import logging

# Magnus logging levels are different to your logging levels.
logger = logging.getLogger("application")
logger.setLevel(logging.DEBUG)


def return_parameter() -> dict:
    return {"x": 1}


def get_parameter(x: int):
    logger.info(f"I got a parameter: {x}")
    print(x)
