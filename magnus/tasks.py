import contextlib
import importlib
import io
import json
import logging
import os
import subprocess
import sys
from typing import ClassVar, Optional

from pydantic import BaseModel, Extra, validator
from stevedore import driver

from magnus import defaults, utils

logger = logging.getLogger(defaults.NAME)


# --8<-- [start:docs]


class BaseTaskType(BaseModel):  # pylint: disable=too-few-public-methods
    """A base task class which does the execution of command defined by the user."""

    task_type: ClassVar[str] = ""
    command: str
    node_name: str

    class Config:
        extra = Extra.forbid

    def _get_parameters(self, map_variable: dict = None, **kwargs) -> dict:
        """Return the parameters in scope for the execution.

        Args:
            map_variable (dict, optional): If the command is part of map node, the value of map. Defaults to None.

        Returns:
            dict: The parameters dictionary in-scope for the task execution
        """
        return utils.get_user_set_parameters(remove=False)

    def execute_command(self, map_variable: dict = None, **kwargs):
        """The function to execute the command.

        And map_variable is sent in as an argument into the function.

        Args:
            map_variable (dict, optional): If the command is part of map node, the value of map. Defaults to None.

        Raises:
            NotImplementedError: Base class, not implemented
        """
        raise NotImplementedError()

    def _set_parameters(self, parameters: dict = None, **kwargs):
        """Set the parameters back to the environment variables.

        Args:
            parameters (dict, optional): The parameters to set back as env variables. Defaults to None.
        """
        # Nothing to do
        if not parameters:
            return

        if not isinstance(parameters, dict):
            msg = (
                f"call to function {self.command} returns of type: {type(parameters)}. "
                "Only dictionaries are supported as return values for functions as part part of magnus pipeline."
            )
            logger.warn(msg)
            return

        for key, value in parameters.items():
            logger.info(f"Setting User defined parameter {key} with value: {value}")
            os.environ[defaults.PARAMETER_PREFIX + key] = json.dumps(value)

    @contextlib.contextmanager
    def output_to_file(self, map_variable: dict = None):
        """Context manager to put the output of a function execution to catalog.

        Args:
            map_variable (dict, optional): If the command is part of map node, the value of map. Defaults to None.

        """
        from magnus import put_in_catalog  # Causing cyclic imports

        log_file_name = self.node_name.replace(" ", "_")
        if map_variable:
            for _, value in map_variable.items():
                log_file_name += "_" + str(value)

        log_file = open(log_file_name, "w")

        f = io.StringIO()
        try:
            with contextlib.redirect_stdout(f):
                yield
        finally:
            print(f.getvalue())  # print to console
            log_file.write(f.getvalue())  # Print to file

            f.close()
            log_file.close()
            put_in_catalog(log_file.name)
            os.remove(log_file.name)


# --8<-- [end:docs]


class PythonTaskType(BaseTaskType):  # pylint: disable=too-few-public-methods
    """The task class for python command."""

    task_type: ClassVar[str] = "python"

    def execute_command(self, map_variable: dict = None, **kwargs):
        """Execute the notebook as defined by the command."""
        module, func = utils.get_module_and_func_names(self.command)
        sys.path.insert(0, os.getcwd())  # Need to add the current directory to path
        imported_module = importlib.import_module(module)
        f = getattr(imported_module, func)

        parameters = self._get_parameters()
        filtered_parameters = utils.filter_arguments_for_func(f, parameters, map_variable)

        if map_variable:
            os.environ[defaults.PARAMETER_PREFIX + "MAP_VARIABLE"] = json.dumps(map_variable)

        logger.info(f"Calling {func} from {module} with {filtered_parameters}")

        with self.output_to_file(map_variable=map_variable) as _:
            try:
                user_set_parameters = f(**filtered_parameters)
            except Exception as _e:
                msg = f"Call to the function {self.command} with {filtered_parameters} did not succeed.\n"
                logger.exception(msg)
                logger.exception(_e)
                raise

            if map_variable:
                del os.environ[defaults.PARAMETER_PREFIX + "MAP_VARIABLE"]

            self._set_parameters(user_set_parameters)


class PythonLambdaTaskType(BaseTaskType):  # pylint: disable=too-few-public-methods
    """The task class for python-lambda command."""

    task_type: ClassVar[str] = "python-lambda"

    def execute_command(self, map_variable: dict = None, **kwargs):
        """Execute the lambda function as defined by the command.

        Args:
            map_variable (dict, optional): If the node is part of an internal branch. Defaults to None.

        Raises:
            Exception: If the lambda function has _ or __ in it that can cause issues.
        """
        if "_" in self.command or "__" in self.command:
            msg = (
                f"Command given to {self.task_type} cannot have _ or __ in them. "
                "The string is supposed to be for simple expressions only."
            )
            raise Exception(msg)

        f = eval(self.command)

        parameters = self._get_parameters()
        filtered_parameters = utils.filter_arguments_for_func(f, parameters, map_variable)

        if map_variable:
            os.environ[defaults.PARAMETER_PREFIX + "MAP_VARIABLE"] = json.dumps(map_variable)

        logger.info(f"Calling lambda function: {self.command} with {filtered_parameters}")
        try:
            user_set_parameters = f(**filtered_parameters)
        except Exception as _e:
            msg = f"Call to the function {self.command} with {filtered_parameters} did not succeed.\n"
            logger.exception(msg)
            logger.exception(_e)
            raise

        if map_variable:
            del os.environ[defaults.PARAMETER_PREFIX + "MAP_VARIABLE"]

        self._set_parameters(user_set_parameters)


class NotebookTaskType(BaseTaskType):
    """The task class for Notebook based execution."""

    task_type: ClassVar[str] = "notebook"
    notebook_output_path: str = ""
    optional_ploomber_args: dict = {}

    @validator("command")
    def notebook_should_end_with_ipynb(cls, command: str):
        if not command.endswith(".ipynb"):
            raise Exception("Notebook task should point to a ipynb file")

        return command

    @validator("notebook_output_path")
    def correct_notebook_output_path(cls, notebook_output_path: str, values: dict):
        if notebook_output_path:
            return notebook_output_path

        return "".join(values["command"].command.split(".")[:-1]) + "_out.ipynb"

    def execute_command(self, map_variable: dict = None, **kwargs):
        """Execute the python notebook as defined by the command.

        Args:
            map_variable (dict, optional): If the node is part of internal branch. Defaults to None.

        Raises:
            ImportError: If necessary dependencies are not installed
            Exception: If anything else fails
        """
        try:
            import ploomber_engine as pm

            from magnus import put_in_catalog  # Causes issues with cyclic import

            parameters = self._get_parameters()
            filtered_parameters = parameters

            notebook_output_path = self.notebook_output_path

            if map_variable:
                os.environ[defaults.PARAMETER_PREFIX + "MAP_VARIABLE"] = json.dumps(map_variable)

                for _, value in map_variable.items():
                    notebook_output_path += "_" + str(value)

            ploomber_optional_args = self.optional_ploomber_args  # type: ignore

            kwds = {
                "input_path": self.command,
                "output_path": notebook_output_path,
                "parameters": filtered_parameters,
                "log_output": True,
                "progress_bar": False,
            }

            kwds.update(ploomber_optional_args)

            pm.execute_notebook(**kwds)

            put_in_catalog(notebook_output_path)
            if map_variable:
                del os.environ[defaults.PARAMETER_PREFIX + "MAP_VARIABLE"]

        except ImportError as e:
            msg = (
                "Task type of notebook requires ploomber engine to be installed. Please install via optional: notebook"
            )
            raise Exception(msg) from e


class ShellTaskType(BaseTaskType):
    """The task class for shell based commands."""

    task_type: ClassVar[str] = "shell"

    def execute_command(self, map_variable: dict = None, **kwargs):
        # Using shell=True as we want to have chained commands to be executed in the same shell.
        # TODO can we do this without shell=True.
        """Execute the shell command as defined by the command.

        Args:
            map_variable (dict, optional): If the node is part of an internal branch. Defaults to None.
        """
        subprocess_env = os.environ.copy()

        if map_variable:
            subprocess_env[defaults.PARAMETER_PREFIX + "MAP_VARIABLE"] = json.dumps(map_variable)

        with subprocess.Popen(
            self.command,
            shell=True,
            env=subprocess_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ) as proc, self.output_to_file(map_variable=map_variable) as _:
            for line in proc.stdout:  # type: ignore
                logger.info(line)
                print(line)

            proc.wait()
            if proc.returncode != 0:
                raise Exception("Command failed")


class ContainerTaskType(BaseTaskType):
    """
    TODO: This is not fully done
    The task class for container based execution.
    """

    task_type: ClassVar[str] = "container"
    image: str

    def execute_command(self, map_variable: dict = None, **kwargs):
        # Conditional import
        try:
            import docker  # pylint: disable=C0415

            client = docker.from_env()
        except ImportError as e:
            msg = "Task type of container requires docker to be installed. Please install via optional: docker"
            logger.exception(msg)
            raise Exception(msg) from e
        except Exception as ex:
            logger.exception("Could not get access to docker")
            raise Exception("Could not get the docker socket file, do you have docker installed?") from ex

        container_env_variables = {}

        for key, value in self._get_parameters().items():
            container_env_variables[defaults.PARAMETER_PREFIX + key] = value

        if map_variable:
            container_env_variables[defaults.PARAMETER_PREFIX + "MAP_VARIABLE"] = json.dumps(map_variable)

        try:
            container = client.containers.create(
                image=self.config.image,
                command=self.command,
                auto_remove=False,
                network_mode="host",
                environment=container_env_variables,
            )
            container.start()
            stream = container.logs(stream=True, follow=True)
            while True:
                try:
                    output = next(stream).decode("utf-8")
                    output = output.strip("\r\n")
                    logger.info(output)
                except StopIteration:
                    logger.info("Docker Run completed")
                    break

        except Exception as _e:
            logger.exception("Problems with spinning up the container")
            raise _e


def create_task(
    node_name: str,
    command: str,
    image: str = "",
    command_type: str = defaults.COMMAND_TYPE,
    command_config: Optional[dict] = None,
) -> BaseTaskType:
    """
    Creates a task object from the command configuration.

    Args:
        command (str): The command to run
        image (str, optional): Only in case of a container based command. Defaults to "".
        command_type (str, optional): The command type. Defaults to defaults.COMMAND_TYPE, python
        command_config (Optional[dict], optional): Any optional command config. Defaults to None.

    Returns:
        tasks.BaseTaskType: The command object
    """
    # If we want to run a container, we need to know which container.
    if command_type == ContainerTaskType.task_type and not image:
        msg = "Image is required when trying to run a container task type"
        logger.exception(msg)
        raise Exception(msg)

    command_config = command_config or {}
    command_config["command"] = command
    command_config["node_name"] = node_name

    if image:
        command_config["image"] = image

    try:
        task_mgr = driver.DriverManager(
            namespace="tasks",
            name=command_type,
            invoke_on_load=True,
            invoke_kwds=command_config,
        )
        return task_mgr.driver
    except Exception as _e:
        msg = (
            f"Could not find the task type {command_type}. Please ensure you have installed "
            "the extension that provides the node type."
        )
        raise Exception(msg) from _e
