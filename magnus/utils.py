from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from collections import OrderedDict
from datetime import datetime
from inspect import signature
from pathlib import Path
from string import Template as str_template
from types import FunctionType
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Tuple, Union

from ruamel.yaml import YAML
from stevedore import driver

import magnus.context as context
from magnus import defaults, names

if TYPE_CHECKING:
    from magnus.extensions.nodes import TaskNode
    from magnus.nodes import BaseNode


logger = logging.getLogger(defaults.LOGGER_NAME)
logging.getLogger("stevedore").setLevel(logging.CRITICAL)


def does_file_exist(file_path: str) -> bool:
    """Check if a file exists.
    Implemented here to avoid repetition of logic.

    Args:
        file_path (str): The file path to check

    Returns:
        bool: False if it does not otherwise True
    """
    my_file = Path(file_path)
    return my_file.is_file()


def does_dir_exist(file_path: Union[str, Path]) -> bool:
    """Check if a directory exists.
    Implemented here to avoid repetition of logic.

    Args:
        file_path (str or Path): The directory path to check

    Returns:
        bool: False if the directory does not exist, True otherwise
    """
    my_file = Path(file_path)
    return my_file.is_dir()


def safe_make_dir(directory: Union[str, Path]):
    """Safely make the directory.
    Ignore if it exists and create the parents if necessary.

    Args:
        directory (str): The directory path to create
    """
    Path(directory).mkdir(parents=True, exist_ok=True)


def generate_run_id(run_id: str = None) -> str:
    """Generate a new run_id.

    If the input run_id is none, we create one based on time stamp.

    Args:
        run_id (str, optional): Input Run ID. Defaults to None

    Returns:
        str: A generated run_id
    """
    # If we are not provided with a run_id, generate one
    if not run_id:
        now = datetime.now()
        run_id = f"{names.get_random_name()}-{now.hour:02}{now.minute:02}"

    return run_id


def apply_variables(apply_to: Dict[str, Any], variables: Dict[str, str]) -> Dict[str, Any]:
    """Safely applies the variables to a config.

    For example: For config:
         {'a' : ${b}}, the value of ${b} is replaced by b in the variables.

    If the ${b} does not exist in the variables, it is ignored in the config.

    Args:
        apply_to (dict): The config to apply variables
        variables (dict): The variables in key, value pairs

    Raises:
        Exception: If the variables is not dict

    Returns:
        dict: A transformed dict with variables applied
    """
    if not isinstance(variables, dict):
        raise Exception("Argument Variables should be dict")

    json_d = json.dumps(apply_to)
    transformed = str_template(json_d).safe_substitute(**variables)
    return json.loads(transformed)


def get_module_and_func_names(command: str) -> Tuple[str, str]:
    """Given a string of module.function, this functions returns the module name and func names.

    It also checks to make sure that the string is of expected 'module.func' format

    Args:
        command (str): String of format module.function_name

    Raises:
        Exception: If the string is of not format

    Returns:
        Tuple[str, str]: (module_name, function_name) extracted from the input string
    """
    mods = command.split(".")
    if len(mods) <= 1:
        raise Exception("The command should be a function to call")
    func = mods[-1]
    module = ".".join(mods[:-1])
    return module, func


def get_module_and_func_from_function(command: FunctionType) -> str:
    """Given a function, this function returns the module name and func names.

    Args:
        command (FunctionType): The function to extract the module and func names from

    Returns:
        str: the module and function in module.func format.
    """
    module_name = sys.modules[command.__module__]
    func_name = command.__name__
    return f"{module_name}.{func_name}"


def get_dag_hash(dag: Dict[str, Any]) -> str:
    """Generates the hash of the dag definition.

    Args:
        dag (dict): The dictionary object containing the dag definition

    Returns:
        str: The hash of the dag definition
    """
    dag_str = json.dumps(dag, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(dag_str.encode("utf-8")).hexdigest()


def load_yaml(file_path: str, load_type: str = "safe") -> Dict[str, Any]:
    """Loads an yaml and returns the dictionary.

    Args:
        file_path (str): The path of the yamlfile
        load_type (str, optional): The load type as understood by ruamel. Defaults to 'safe'.

    Returns:
        dict: The mapping as defined in the yaml file
    """
    with open(file_path, encoding="utf-8") as f:
        yaml = YAML(typ=load_type, pure=True)
        yaml_config = yaml.load(f)
    return yaml_config


def is_a_git_repo() -> bool:
    """Does a git command to see if the project is git versioned.

    Returns:
        bool: True if it is git versioned, False otherwise
    """
    command = "git rev-parse --is-inside-work-tree"
    try:
        subprocess.check_output(command.split()).strip().decode("utf-8")
        logger.info("Found the code to be git versioned")
        return True
    except BaseException:  # pylint: disable=W0702
        logger.error("No git repo found, unsafe hash")

    return False


def get_current_code_commit() -> Union[str, None]:
    """Gets the git sha id if the project is version controlled.

    Returns:
        Union[str, None]: SHA ID if the code is versioned, None otherwise
    """
    command = "git rev-parse HEAD"
    if not is_a_git_repo():
        return None
    try:
        label = subprocess.check_output(command.split()).strip().decode("utf-8")
        logger.info("Found the git commit to be: %s", label)
        return label
    except BaseException:  # pylint: disable=W0702
        logger.exception("Error getting git hash")
        raise


def archive_git_tracked(name: str):
    """Generate a git archive of the tracked files.

    Args:
        name (str): The name to give the archive

    Raises:
        Exception: If its not a git repo
    """
    command = f"git archive -v -o {name}.tar.gz --format=tar.gz HEAD"

    if not is_a_git_repo():
        raise Exception("Not a git repo")
    try:
        subprocess.check_output(command.split()).strip().decode("utf-8")
    except BaseException:  # pylint: disable=W0702
        logger.exception("Error archiving repo")
        raise


def is_git_clean() -> Tuple[bool, Union[None, str]]:
    """Checks if the git tree is clean and there are no modified tracked files.

    Returns:
        Tuple[bool, Union[None, str]]: None if its clean, comma-seperated file names if it is changed
    """
    command = "git diff --name-only"
    if not is_a_git_repo():
        return False, None
    try:
        label = subprocess.check_output(command.split()).strip().decode("utf-8")
        if not label:
            return True, None
        return False, label
    except BaseException:  # pylint: disable=W0702
        logger.exception("Error checking if the code is git clean")

    return False, None


def get_git_remote() -> Union[str, None]:
    """Gets the remote URL of git.

    Returns:
        Union[str, None]: Remote URL if the code is version controlled, None otherwise
    """
    command = "git config --get remote.origin.url"
    if not is_a_git_repo():
        return None
    try:
        label = subprocess.check_output(command.split()).strip().decode("utf-8")
        logger.info("Found the git remote to be: %s", label)
        return label
    except BaseException:  # pylint: disable=W0702
        logger.exception("Error getting git remote")
        raise


def get_local_docker_image_id(image_name: str) -> str:
    """If we are running in local settings, return the docker image id.

    Args:
        image_name (str): The image name we need the digest for

    Returns:
        str: The docker image digest
    """
    try:
        import docker

        client = docker.from_env()
        image = client.images.get(image_name)
        return image.attrs["Id"]
    except ImportError:  # pragma: no cover
        logger.warning("Did not find docker installed, some functionality might be affected")
    except BaseException:
        logger.exception(f"Could not find the image by name {image_name}")

    return ""


def get_git_code_identity(run_log_store):
    """Returns a code identity object for version controlled code.

    Args:
        run_log_store (magnus.datastore.BaseRunLogStore): The run log store used in this process

    Returns:
        magnus.datastore.CodeIdentity: The code identity used by the run log store.
    """
    code_identity = run_log_store.create_code_identity()
    try:
        code_identity.code_identifier = get_current_code_commit()
        code_identity.code_identifier_type = "git"
        code_identity.code_identifier_dependable, changed = is_git_clean()
        code_identity.code_identifier_url = get_git_remote()
        if changed:
            code_identity.code_identifier_message = "changes found in " + ", ".join(changed.split("\n"))
    except BaseException:
        logger.exception("Git code versioning problems")

    return code_identity


def remove_prefix(text: str, prefix: str) -> str:
    """Removes a prefix if one is present in the input text.

    Args:
        text (str): The input text to remove the prefix from
        prefix (str): The prefix that has to be removed

    Returns:
        str: The original string if no prefix is found, or the right prefix chomped string if present
    """
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text  # or whatever is given


def get_tracked_data() -> Dict[str, str]:
    """Scans the environment variables to find any user tracked variables that have a prefix MAGNUS_TRACK_
    Removes the environment variable to prevent any clashes in the future steps.

    Returns:
        dict: A dictionary of user tracked data
    """
    tracked_data = {}
    for env_var, value in os.environ.items():
        if env_var.startswith(defaults.TRACK_PREFIX):
            key = remove_prefix(env_var, defaults.TRACK_PREFIX)
            tracked_data[key.lower()] = json.loads(value)
            del os.environ[env_var]
    return tracked_data


def get_user_set_parameters(remove: bool = False) -> Dict[str, str]:
    """Scans the environment variables for any user returned parameters that have a prefix MAGNUS_PRM_.

    Args:
        remove (bool, optional): Flag to remove the parameter if needed. Defaults to False.

    Returns:
        dict: The dictionary of found user returned parameters
    """
    parameters = {}
    for env_var, value in os.environ.items():
        if env_var.startswith(defaults.PARAMETER_PREFIX):
            key = remove_prefix(env_var, defaults.PARAMETER_PREFIX)
            try:
                parameters[key.lower()] = json.loads(value)
            except json.decoder.JSONDecodeError:
                logger.error(f"Parameter {key} could not be JSON decoded, adding the literal value")
                parameters[key.lower()] = value

            if remove:
                del os.environ[env_var]
    return parameters


def diff_dict(d1: Dict[str, Any], d2: Dict[str, Any]) -> Dict[str, Any]:
    """Given two dicts d1 and d2, return a new dict that has upsert items from d1.

    Args:
        d1 (reference): The reference dict.
        d2 (compare): Any new or modified items compared to d1 would be returned back

    Returns:
        dict: Any new or modified items in d2 in comparison to d1 would be sent back
    """
    diff = {}

    for k2, v2 in d2.items():
        if k2 in d1 and d1[k2] != v2:
            diff[k2] = v2
            continue
        diff[k2] = v2

    return diff


def hash_bytestr_iter(bytesiter, hasher, ashexstr=True):  # pylint: disable=C0116
    """Hashes the given bytesiter using the given hasher."""
    for block in bytesiter:  # pragma: no cover
        hasher.update(block)
    return hasher.hexdigest() if ashexstr else hasher.digest()  # pragma: no cover


def file_as_blockiter(afile, blocksize=65536):  # pylint: disable=C0116
    """From a StackOverflow answer: that is used to generate a MD5 hash of a large files.
    # https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file.

    """
    with afile:  # pragma: no cover
        block = afile.read(blocksize)
        while len(block) > 0:
            yield block
            block = afile.read(blocksize)


def get_data_hash(file_name: str):
    """Returns the hash of the data file.

    Args:
        file_name (str): The file name to generated the hash

    Returns:
        str: The SHA ID of the file contents
    """
    # https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file
    return hash_bytestr_iter(file_as_blockiter(open(file_name, "rb")), hashlib.sha256())  # pragma: no cover


def filter_arguments_for_func(
    func: Callable[[Any], Dict[str, Any]], parameters: Dict[str, Any], map_variable: Dict[str, str] = None
) -> Dict[str, Any]:
    """Inspects the function to be called as part of the pipeline to find the arguments of the function.
    Matches the function arguments to the parameters available either by command line or by up stream steps.

    Args:
        func (Callable): The function to inspect
        parameters (dict): The parameters available for the run

    Returns:
        dict: The parameters matching the function signature
    """
    sign = signature(func)
    return filter_arguments_from_parameters(
        parameters=parameters,
        signature_parameters=sign.parameters,
        map_variable=map_variable,
    )


def filter_arguments_from_parameters(
    parameters: Dict[str, Any],
    signature_parameters: Union[List, Mapping],
    map_variable: dict = None,
) -> dict:
    """Filters the given parameters based on the signature of the function.

    Args:
        parameters (dict): All the parameters available for the run
        signature_parameters (Union[List, Mapping]): The arguments of the function signature
        map_variable (dict, optional): If the function is part of a map step. Defaults to None.

    Returns:
        dict: The filtered parameters of the function.
    """
    arguments = {}

    for param, value in parameters.items():
        if param in signature_parameters:
            arguments[param] = value

    if map_variable:
        for iterate_as, value in map_variable.items():
            if iterate_as in signature_parameters:
                arguments[iterate_as] = value

    return arguments


def get_node_execution_command(
    node: BaseNode,
    map_variable: dict = None,
    over_write_run_id: str = "",
) -> str:
    """A utility function to standardize execution call to a node via command line.

    Args:
        executor (object): The executor class.
        node (object): The Node to execute
        map_variable (str, optional): If the node belongs to a map step. Defaults to None.

    Returns:
        str: The execution command to run a node via command line.
    """
    run_id = context.run_context.run_id

    if over_write_run_id:
        run_id = over_write_run_id

    log_level = logging.getLevelName(logger.getEffectiveLevel())

    action = f"magnus execute_single_node {run_id} " f"{node._command_friendly_name()}" f" --log-level {log_level}"

    if context.run_context.pipeline_file:
        action = action + f" --file {context.run_context.pipeline_file}"

    if map_variable:
        action = action + f" --map-variable '{json.dumps(map_variable)}'"

    if context.run_context.configuration_file:
        action = action + f" --config-file {context.run_context.configuration_file}"

    if context.run_context.parameters_file:
        action = action + f" --parameters-file {context.run_context.parameters_file}"

    if context.run_context.tag:
        action = action + f" --tag {context.run_context.tag}"

    return action


def get_fan_command(
    mode: str,
    node: BaseNode,
    run_id: str,
    map_variable: dict = None,
) -> str:
    """
    An utility function to return the fan "in or out" command

    Args:
        executor (BaseExecutor): The executor class
        mode (str): in or out
        node (BaseNode): The composite node that we are fanning in or out
        run_id (str): The run id.
        map_variable (dict, optional): If the node is a map, we have the map variable. Defaults to None.

    Returns:
        str: The fan in or out command
    """
    log_level = logging.getLevelName(logger.getEffectiveLevel())
    action = (
        f"magnus fan {run_id} "
        f"{node._command_friendly_name()} "
        f"--mode {mode} "
        f"--file {context.run_context.pipeline_file} "
        f"--log-level {log_level} "
    )
    if context.run_context.configuration_file:
        action = action + f" --config-file {context.run_context.configuration_file} "

    if context.run_context.parameters_file:
        action = action + f" --parameters-file {context.run_context.parameters_file}"

    if map_variable:
        action = action + f" --map-variable '{json.dumps(map_variable)}'"

    if context.run_context.tag:
        action = action + f" --tag {context.run_context.tag}"

    return action


def get_job_execution_command(node: TaskNode, over_write_run_id: str = "") -> str:
    """Get the execution command to run a job via command line.

    This function should be used by all executors to submit jobs in remote environment

    Args:
        executor (BaseExecutor): The executor class.
        node (BaseNode): The node being executed.
        over_write_run_id (str, optional): If the node is part of a map step. Defaults to ''.

    Returns:
        str: The execution command to run a job via command line.
    """

    run_id = context.run_context.run_id

    if over_write_run_id:
        run_id = over_write_run_id

    log_level = logging.getLevelName(logger.getEffectiveLevel())

    cli_command, cli_options = node.executable.get_cli_options()

    action = f"magnus execute_{cli_command} {run_id} " f" --log-level {log_level}"

    action = action + f" --entrypoint {defaults.ENTRYPOINT.SYSTEM.value}"

    if context.run_context.configuration_file:
        action = action + f" --config-file {context.run_context.configuration_file}"

    if context.run_context.parameters_file:
        action = action + f" --parameters-file {context.run_context.parameters_file}"

    if context.run_context.tag:
        action = action + f" --tag {context.run_context.tag}"

    for key, value in cli_options.items():
        action = action + f" --{key} {value}"

    return action


def get_provider_by_name_and_type(service_type: str, service_details: defaults.ServiceConfig):
    """Given a service type, one of executor, run_log_store, catalog, secrets and the config
    return the exact child class implementing the service.
    We use stevedore to do the work for us.

    Args:
        service_type (str): One of executor, run_log_store, catalog, secrets
        service_details (dict): The config used to instantiate the service.

    Raises:
        Exception: If the service by that name does not exist

    Returns:
        object: A service object
    """
    namespace = service_type

    service_name = service_details["type"]
    service_config: Mapping[str, Any] = {}
    if "config" in service_details:
        service_config = service_details.get("config", {})

    logger.info(f"Trying to get a service of {service_type} of the name {service_name} with config: {service_config}")
    try:
        mgr = driver.DriverManager(
            namespace=namespace,
            name=service_name,
            invoke_on_load=True,
            invoke_kwds={**service_config},
        )
        return mgr.driver
    except Exception as _e:
        raise Exception(f"Could not find the service of type: {service_type} with config: {service_details}") from _e


def get_duration_between_datetime_strings(start_time: str, end_time: str) -> str:
    """Given two datetime strings, compute the duration between them.

    Args:
        start_time (str): ISO format datetime string
        end_time (str): ISO format datetime string
    Returns:
        The duration between the time in string format
    """
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    return str(end - start)


def get_run_config() -> dict:
    """Given an executor with assigned services, return the run_config.

    Args:
        executor (object): The executor with all the services assigned.

    Returns:
        dict: The run_config.
    """

    run_config = context.run_context.dict()
    return run_config

    # run_config["executor"] = {"type": run_context.executor.service_name, "config": run_context.executor.dict()}

    # run_config["run_log_store"] = {
    #     "type": run_context.run_log_store.service_name,
    #     "config": run_context.run_log_store.dict(),
    # }

    # run_config["catalog"] = {
    #     "type": run_context.catalog_handler.service_name,
    #     "config": run_context.catalog_handler.dict(),
    # }

    # run_config["secrets"] = {
    #     "type": run_context.secrets_handler.service_name,
    #     "config": run_context.secrets_handler.dict(),
    # }

    # run_config["experiment_tracker"] = {
    #     "type": run_context.experiment_tracker.service_name,
    #     "config": run_context.experiment_tracker.dict(),
    # }
    # run_config["variables"] = run_context.variables

    # if run_context.dag:
    #     # Some executions do not define a dag
    #     run_config["pipeline"] = run_context.dag._to_dict()

    # return run_config


def json_to_ordered_dict(json_str: str) -> OrderedDict:
    """Decode a JSON str into OrderedDict.

    Args:
        json_str ([str]): The JSON string to decode

    Returns:
        [OrderedDict]: The decoded OrderedDict
    """
    if json_str and json_str != "{}":
        return json.loads(json_str, object_pairs_hook=OrderedDict)

    return OrderedDict()


def set_magnus_environment_variables(run_id: str = None, configuration_file: str = None, tag: str = None):
    """Set the environment variables used by magnus. This function should be called during the prepare configurations
    by all executors.

    Args:
        run_id (str, optional): The run id of the execution. Defaults to None.
        configuration_file (str, optional): The configuration file if used. Defaults to None.
        tag (str, optional): The tag associated with a run. Defaults to None.
    """
    if run_id:
        os.environ[defaults.ENV_RUN_ID] = run_id

    if configuration_file:
        os.environ[defaults.MAGNUS_CONFIG_FILE] = configuration_file

    if tag:
        os.environ[defaults.MAGNUS_RUN_TAG] = tag


def gather_variables() -> dict:
    """Gather all the environment variables used by magnus. All the variables start with MAGNUS_VAR_.

    Returns:
        dict: All the environment variables present in the environment.
    """
    variables = {}

    for env_var, value in os.environ.items():
        if env_var.startswith(defaults.VARIABLE_PREFIX):
            key = remove_prefix(env_var, defaults.VARIABLE_PREFIX)
            variables[key] = value

    return variables
