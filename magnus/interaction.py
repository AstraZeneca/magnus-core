import json
import logging
import os
from pathlib import Path
from typing import Callable, Union

from magnus import defaults, exceptions, graph, pipeline, utils

logger = logging.getLogger(defaults.NAME)


def track_this(**kwargs):
    """
    Set up the keyword args as environment variables for tracking purposes as
    part pf the run.

    For every key-value pair found in kwargs, we set up an environmental variable of
    MAGNUS_TRACK_key = json.dumps(value)

    Args:
        kwargs (dict): The dictionary of key value pairs to track.
    """
    from magnus.pipeline import \
        global_executor  # pylint: disable=import-outside-toplevel
    for key, value in kwargs.items():
        logger.info(f'Tracking {key} with value: {value}')
        os.environ[defaults.TRACK_PREFIX + key] = json.dumps(value)
        global_executor.experiment_tracker.set_metric(key, value)


def store_parameter(**kwargs: dict):
    """
    Set up the keyword args as environment variables for parameters tracking
    purposes as part pf the run.

    For every key-value pair found in kwargs, we set up an environmental variable of
    MAGNUS_PRM_key = json.dumps(value)
    """
    for key, value in kwargs.items():
        logger.info(f'Storing parameter {key} with value: {value}')
        os.environ[defaults.PARAMETER_PREFIX + key] = json.dumps(value)


def get_parameter(key=None) -> Union[str, dict]:
    """
    Get the parameter set as part of the user convenience function.

    We do not remove the parameter from the environment in this phase as
    as the function execution has not been completed.

    Returns all the parameters, if no key was provided.

    Args:
        key (str, optional): The parameter key to retrieve. Defaults to None.

    Raises:
        Exception: If the menionted key was not part of the paramters

    Returns:
        Union[str, dict]: A single value of str or a dictionary if no key was specified
    """
    parameters = utils.get_user_set_parameters(remove=False)
    if not key:
        return parameters
    if key not in parameters:
        raise Exception(f'Parameter {key} is not set before')
    return parameters[key]


def get_secret(secret_name: str = None) -> str:
    """
    Get a secret by the name from the secrets manager

    Args:
        secret_name (str): The name of the secret to get. Defaults to None.

    Returns:
        str: The secret from the secrets manager, if exists. If the requested secret was None, we return all.
        Otherwise, raises exception.

    Raises:
        exceptions.SecretNotFoundError: Secret not found in the secrets manager.
    """
    from magnus.pipeline import \
        global_executor  # pylint: disable=import-outside-toplevel
    secrets_handler = global_executor.secrets_handler  # type: ignore

    try:
        return secrets_handler.get(name=secret_name)
    except exceptions.SecretNotFoundError:
        logger.exception(f'No secret by the name {secret_name} found in the store')
        raise


def get_from_catalog(name: str, destination_folder: str = None):
    """
    A convenience interaction function to get file from the catalog and place it in the destination folder

    Note: We do not perform any kind of serialization/deserialization in this way.
    Args:
        name (str): The name of the file to get from the catalog
        destination_folder (None): The place to put the file. defaults to compute data folder

    """
    from magnus.pipeline import \
        global_executor  # pylint: disable=import-outside-toplevel

    if not destination_folder:
        destination_folder = global_executor.catalog_handler.compute_data_folder  # type: ignore

    global_executor.catalog_handler.get(name, run_id=global_executor.run_id,  # type: ignore
                                        compute_data_folder=destination_folder)


def put_in_catalog(filepath: str):
    """
    A convenience interaction function to put the file in the catalog.

    Note: We do not perform any kind of serialization/deserialization in this way.

    Args:
        filepath (str): The path of the file to put in the catalog
    """
    from magnus.pipeline import \
        global_executor  # pylint: disable=import-outside-toplevel

    file_path = Path(filepath)

    global_executor.catalog_handler.put(file_path.name, run_id=global_executor.run_id,  # type: ignore
                                        compute_data_folder=file_path.parent)


def get_run_id() -> str:
    """
    Returns the run_id of the current run
    """
    from magnus.pipeline import \
        global_executor  # pylint: disable=import-outside-toplevel

    return global_executor.run_id


def store_run_id():
    """
    Stores the run_id as environment variable for the steps to use.
    """
    run_id = get_run_id()
    os.environ[defaults.ENV_RUN_ID] = run_id


class step(object):

    def __init__(
            self, name: Union[str, callable],
            catalog_config: dict = None, magnus_config: str = None,
            parameters_file: str = None):
        """
        This decorator could be used to make the function within the scope of magnus.

        Args:
            name (str, callable): The name of the step. The step log would have the same name
            catalog_config (dict): The configuration of the catalog per step.
            magnus_config (str): The name of the file having the magnus config, defaults to None.
        """
        if isinstance(name, Callable):
            name = name()
        self.name = name
        self.catalog_config = catalog_config

        configuration = pipeline.get_default_configs()
        if magnus_config:
            configuration = utils.load_yaml(magnus_config)

        run_log_config = configuration.get('run_log_store', defaults.DEFAULT_RUN_LOG_STORE)
        run_log_store = utils.get_provider_by_name_and_type('run_log_store', run_log_config)

        # Catalog handler settings, configuration over-rides everything
        catalog_config = configuration.get('catalog', defaults.DEFAULT_CATALOG)
        catalog_handler = utils.get_provider_by_name_and_type('catalog', catalog_config)

        # Secret handler settings, configuration over-rides everything
        secrets_config = configuration.get('secrets', defaults.DEFAULT_SECRETS)
        secrets_handler = utils.get_provider_by_name_and_type('secrets', secrets_config)

        tracker_config = configuration.get('experiment_tracker', defaults.DEFAULT_EXPERIMENT_TRACKER)
        tracker_handler = utils.get_provider_by_name_and_type('experiment_tracker', tracker_config)

        # Mode configurations, configuration over rides everything
        mode_config = configuration.get('mode', defaults.DEFAULT_EXECUTOR)
        mode_executor = utils.get_provider_by_name_and_type('executor', mode_config)

        run_id = mode_executor.step_decorator_run_id
        if not run_id:
            msg = (
                f'Step decorator expects run id from environment.'
                'For executor of type {mode_executor.service_name}, please provide a value for'
                '{mode_executor.run_id_key_from_env}.'
            )
            raise Exception(msg)

        mode_executor.run_log_store = run_log_store
        mode_executor.catalog_handler = catalog_handler
        mode_executor.secrets_handler = secrets_handler
        mode_executor.experiment_tracker = tracker_handler
        mode_executor.run_id = run_id
        mode_executor.parameters_file = parameters_file
        self.executor = mode_executor
        pipeline.global_executor = self.executor

        try:
            # Try to get it if previous steps have created it
            run_log = self.executor.run_log_store.get_run_log_by_id(self.executor.run_id)
            if run_log.status in [defaults.FAIL, defaults.SUCCESS]:
                msg = (
                    f'The run_log for run_id: {self.run_id} already exists and is in {run_log.status} state.'
                    ' Make sure that this was not run before.'
                )
                raise Exception(msg)
        except exceptions.RunLogNotFoundError:
            # Create one if they are not created
            self.executor.set_up_run_log()

    def __call__(self, func):
        """
        The function is converted into a node and called via the magnus framework.
        """

        def wrapped_f(*args):

            step_config = {
                'command': func,
                'command_type': 'python-function',
                'type': 'task',
                'next': 'not defined',
                'catalog': self.catalog_config
            }
            node = graph.create_node(name=self.name, step_config=step_config)
            self.executor.execute_from_graph(node=node)
            run_log = self.executor.run_log_store.get_run_log_by_id(run_id=self.executor.run_id, full=False)
            print(json.dumps(run_log.dict(), indent=4))
        return wrapped_f
