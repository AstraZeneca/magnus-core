!!! note "Opt out"

    Pipelines need not use the ```catalog``` if they prefer other ways to transfer
    data between tasks. The default configuration of ```do-nothing``` is no-op by design.
    We kindly request to raise a feature request to make us aware of the eco-system.

Catalog provides a way to store and retrieve data generated by the individual steps of the dag to downstream
steps of the dag. It can be any storage system that indexes its data by a unique identifier.

For example, a local directory structure partitioned by a ```run_id``` or S3 bucket prefixed by ```run_id```.

!!! tip inline end "Checkpoint"

    Cataloging happens even if the step execution eventually fails. This behavior
    can be used to recover from a failed run from a checkpoint.



The directory structure within a partition is the same as the project directory structure. This enables you to
get/put data in the catalog as if you are working with local directory structure. Every interaction with the catalog
(either by API or configuration) results in an entry in the [```run log```](../concepts/run-log.md/#step_log)

Internally, magnus also uses the catalog to store execution logs of tasks i.e stdout and stderr from
[python](../concepts/task.md/#python) or [shell](../concepts/task.md/#shell) and executed notebook
from [notebook tasks](../concepts/task.md/#notebook).

Since the catalog captures the data files flowing through the pipeline and the execution logs, it enables you
to debug failed pipelines or keep track of data lineage.




!!! warning "Storage considerations"

    Since the data is stored per-run, it might cause the catalog to inflate.

    Please consider some clean up
    mechanisms to regularly prune catalog for executions that are not relevant.




## Example



=== "Configuration"

    Below is a sample configuration that uses the local file system as a catalog store.
    The default location of the catalog is ```.catalog``` and is configurable.

    Every execution of the pipeline will create a sub-directory of name ```run_id``` to store the artifacts
    generated from the execution of the pipeline.

    ```yaml
    --8<-- "examples/configs/fs-catalog.yaml"
    ```

    1. Use local file system as a central catalog, defaults to ```.catalog```

=== "python sdk"

    In the below example, the steps ```create_content_in_data_folder``` and ```create_content_in_another_folder```
    create content for downstream steps, i.e ```retrieve_content_from_both``` to consume.

    !!! note "Delete?"

        Since we are executing in local compute and creating sub-directory ```another```, it might be mistaken that
        we are not cataloging anything. We delete ```another``` directory between steps
        to demonstrate that we indeed move files in and out of the catalog.

    The highlighted lines in the below example show how to specify the files to get/put from the catalog using python SDK.

    ```python linenums="1" hl_lines="44 52 68"
    --8<-- "examples/concepts/catalog.py"
    ```

=== "yaml"

    In the below example, the steps ```data_create``` and ```another_create``` create content for
    downstream steps, i.e ```retrieve``` to consume.

    !!! note "Delete?"

        Since we are executing in local compute and creating sub-directory ```another```, it might be mistaken that
        we are not cataloging anything. We delete ```another``` directory between steps
        to demonstrate that we indeed move files in and out of the catalog.

    The highlighted lines in the below example show how to specify the files to get/put from the catalog using
    yaml.


    ```yaml linenums="1" hl_lines="19-21 26-28 38-40"
    --8<-- "examples/concepts/catalog.yaml"
    ```

!!! note "glob pattern"

    We use [glob pattern](https://docs.python.org/3/library/glob.html) to search for files.

    Note that, the pattern to recursively match all directories is ```**/*```


The execution results in the ```catalog``` populated with the artifacts and the execution logs of the tasks.


=== "Directory structure"

    The directory structure within the ```catalog``` for the execution, i.e meek-stonebraker-0626, resembles
    the project directory structure.

    The execution logs of all the tasks are also present in the ```catalog```.

    ```
    >>> tree .catalog
    .catalog
    └── meek-stonebraker-0626
        ├── another
        │   └── world.txt
        ├── create_content_in_another_folder.execution.log
        ├── create_content_in_data_folder.execution.log
        ├── data
        │   └── hello.txt
        ├── delete_another_folder.execution.log
        └── retrieve_content_from_both.execution.log

    4 directories, 6 files
    ```

=== "Run log"

    The run log captures the data identities of the data flowing through the catalog.


    ```json linenums="1" hl_lines="38-53 84-99 169-191"
    {
    "run_id": "meek-stonebraker-0626",
    "dag_hash": "",
    "use_cached": false,
    "tag": "",
    "original_run_id": "",
    "status": "SUCCESS",
    "steps": {
        "create_content_in_data_folder": {
            "name": "create_content_in_data_folder",
            "internal_name": "create_content_in_data_folder",
            "status": "SUCCESS",
            "step_type": "task",
            "message": "",
            "mock": false,
            "code_identities": [
                {
                    "code_identifier": "6029841c3737fe1163e700b4324d22a469993bb0",
                    "code_identifier_type": "git",
                    "code_identifier_dependable": true,
                    "code_identifier_url": "https://github.com/AstraZeneca/magnus-core.git",
                    "code_identifier_message": ""
                }
            ],
            "attempts": [
                {
                    "attempt_number": 1,
                    "start_time": "2024-01-06 06:26:56.279278",
                    "end_time": "2024-01-06 06:26:56.284564",
                    "duration": "0:00:00.005286",
                    "status": "SUCCESS",
                    "message": "",
                    "parameters": {}
                }
            ],
            "user_defined_metrics": {},
            "branches": {},
            "data_catalog": [
                {
                    "name": "create_content_in_data_folder.execution.log",
                    "data_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "catalog_relative_path": "meek-stonebraker-0626/create_content_in_data_folder.execution.log",
                    "catalog_handler_location": ".catalog",
                    "stage": "put"
                },
                {
                    "name": "data/hello.txt",
                    "data_hash": "6ccad99847c78bfdc7a459399c9957893675d4fec2d675cec750b50ab4842542",
                    "catalog_relative_path": "meek-stonebraker-0626/data/hello.txt",
                    "catalog_handler_location": ".catalog",
                    "stage": "put"
                }
            ]
        },
        "create_content_in_another_folder": {
            "name": "create_content_in_another_folder",
            "internal_name": "create_content_in_another_folder",
            "status": "SUCCESS",
            "step_type": "task",
            "message": "",
            "mock": false,
            "code_identities": [
                {
                    "code_identifier": "6029841c3737fe1163e700b4324d22a469993bb0",
                    "code_identifier_type": "git",
                    "code_identifier_dependable": true,
                    "code_identifier_url": "https://github.com/AstraZeneca/magnus-core.git",
                    "code_identifier_message": ""
                }
            ],
            "attempts": [
                {
                    "attempt_number": 1,
                    "start_time": "2024-01-06 06:26:56.353734",
                    "end_time": "2024-01-06 06:26:56.357519",
                    "duration": "0:00:00.003785",
                    "status": "SUCCESS",
                    "message": "",
                    "parameters": {}
                }
            ],
            "user_defined_metrics": {},
            "branches": {},
            "data_catalog": [
                {
                    "name": "create_content_in_another_folder.execution.log",
                    "data_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "catalog_relative_path": "meek-stonebraker-0626/create_content_in_another_folder.execution.log",
                    "catalog_handler_location": ".catalog",
                    "stage": "put"
                },
                {
                    "name": "another/world.txt",
                    "data_hash": "869ae2ac8365d5353250fc502b084a28b2029f951ea7da0a6948f82172accdfd",
                    "catalog_relative_path": "meek-stonebraker-0626/another/world.txt",
                    "catalog_handler_location": ".catalog",
                    "stage": "put"
                }
            ]
        },
        "delete_another_folder": {
            "name": "delete_another_folder",
            "internal_name": "delete_another_folder",
            "status": "SUCCESS",
            "step_type": "task",
            "message": "",
            "mock": false,
            "code_identities": [
                {
                    "code_identifier": "6029841c3737fe1163e700b4324d22a469993bb0",
                    "code_identifier_type": "git",
                    "code_identifier_dependable": true,
                    "code_identifier_url": "https://github.com/AstraZeneca/magnus-core.git",
                    "code_identifier_message": ""
                }
            ],
            "attempts": [
                {
                    "attempt_number": 1,
                    "start_time": "2024-01-06 06:26:56.428437",
                    "end_time": "2024-01-06 06:26:56.450148",
                    "duration": "0:00:00.021711",
                    "status": "SUCCESS",
                    "message": "",
                    "parameters": {}
                }
            ],
            "user_defined_metrics": {},
            "branches": {},
            "data_catalog": [
                {
                    "name": "delete_another_folder.execution.log",
                    "data_hash": "a9b49c92ed63cb54a8b02c0271a925d9fac254034ed45df83f3ff24c0bd53ef6",
                    "catalog_relative_path": "meek-stonebraker-0626/delete_another_folder.execution.log",
                    "catalog_handler_location": ".catalog",
                    "stage": "put"
                }
            ]
        },
        "retrieve_content_from_both": {
            "name": "retrieve_content_from_both",
            "internal_name": "retrieve_content_from_both",
            "status": "SUCCESS",
            "step_type": "task",
            "message": "",
            "mock": false,
            "code_identities": [
                {
                    "code_identifier": "6029841c3737fe1163e700b4324d22a469993bb0",
                    "code_identifier_type": "git",
                    "code_identifier_dependable": true,
                    "code_identifier_url": "https://github.com/AstraZeneca/magnus-core.git",
                    "code_identifier_message": ""
                }
            ],
            "attempts": [
                {
                    "attempt_number": 1,
                    "start_time": "2024-01-06 06:26:56.520948",
                    "end_time": "2024-01-06 06:26:56.530135",
                    "duration": "0:00:00.009187",
                    "status": "SUCCESS",
                    "message": "",
                    "parameters": {}
                }
            ],
            "user_defined_metrics": {},
            "branches": {},
            "data_catalog": [
                {
                    "name": "data/hello.txt",
                    "data_hash": "6ccad99847c78bfdc7a459399c9957893675d4fec2d675cec750b50ab4842542",
                    "catalog_relative_path": "data/hello.txt",
                    "catalog_handler_location": ".catalog",
                    "stage": "get"
                },
                {
                    "name": "another/world.txt",
                    "data_hash": "869ae2ac8365d5353250fc502b084a28b2029f951ea7da0a6948f82172accdfd",
                    "catalog_relative_path": "another/world.txt",
                    "catalog_handler_location": ".catalog",
                    "stage": "get"
                },
                {
                    "name": "retrieve_content_from_both.execution.log",
                    "data_hash": "0a085cb15df6c70c5859b44cc62bfdc98383600ba4f2983124375a4f64f1ae83",
                    "catalog_relative_path": "meek-stonebraker-0626/retrieve_content_from_both.execution.log",
                    "catalog_handler_location": ".catalog",
                    "stage": "put"
                }
            ]
        },
        "success": {
            "name": "success",
            "internal_name": "success",
            "status": "SUCCESS",
            "step_type": "success",
            "message": "",
            "mock": false,
            "code_identities": [
                {
                    "code_identifier": "6029841c3737fe1163e700b4324d22a469993bb0",
                    "code_identifier_type": "git",
                    "code_identifier_dependable": true,
                    "code_identifier_url": "https://github.com/AstraZeneca/magnus-core.git",
                    "code_identifier_message": ""
                }
            ],
            "attempts": [
                {
                    "attempt_number": 1,
                    "start_time": "2024-01-06 06:26:56.591948",
                    "end_time": "2024-01-06 06:26:56.592032",
                    "duration": "0:00:00.000084",
                    "status": "SUCCESS",
                    "message": "",
                    "parameters": {}
                }
            ],
            "user_defined_metrics": {},
            "branches": {},
            "data_catalog": []
        }
    },
    "parameters": {},
    "run_config": {
        "executor": {
            "service_name": "local",
            "service_type": "executor",
            "enable_parallel": false,
            "placeholders": {}
        },
        "run_log_store": {
            "service_name": "buffered",
            "service_type": "run_log_store"
        },
        "secrets_handler": {
            "service_name": "do-nothing",
            "service_type": "secrets"
        },
        "catalog_handler": {
            "service_name": "file-system",
            "service_type": "catalog"
        },
        "experiment_tracker": {
            "service_name": "do-nothing",
            "service_type": "experiment_tracker"
        },
        "pipeline_file": "",
        "parameters_file": "",
        "configuration_file": "examples/configs/fs-catalog.yaml",
        "tag": "",
        "run_id": "meek-stonebraker-0626",
        "variables": {},
        "use_cached": false,
        "original_run_id": "",
        "dag": {
            "start_at": "create_content_in_data_folder",
            "name": "",
            "description": "",
            "internal_branch_name": "",
            "steps": {
                "create_content_in_data_folder": {
                    "type": "task",
                    "name": "create_content_in_data_folder",
                    "internal_name": "create_content_in_data_folder",
                    "internal_branch_name": "",
                    "is_composite": false
                },
                "create_content_in_another_folder": {
                    "type": "task",
                    "name": "create_content_in_another_folder",
                    "internal_name": "create_content_in_another_folder",
                    "internal_branch_name": "",
                    "is_composite": false
                },
                "retrieve_content_from_both": {
                    "type": "task",
                    "name": "retrieve_content_from_both",
                    "internal_name": "retrieve_content_from_both",
                    "internal_branch_name": "",
                    "is_composite": false
                },
                "delete_another_folder": {
                    "type": "task",
                    "name": "delete_another_folder",
                    "internal_name": "delete_another_folder",
                    "internal_branch_name": "",
                    "is_composite": false
                },
                "success": {
                    "type": "success",
                    "name": "success",
                    "internal_name": "success",
                    "internal_branch_name": "",
                    "is_composite": false
                },
                "fail": {
                    "type": "fail",
                    "name": "fail",
                    "internal_name": "fail",
                    "internal_branch_name": "",
                    "is_composite": false
                }
            }
        },
        "dag_hash": "",
        "execution_plan": "chained"
    }
    }
    ```



## Using python API

Files could also be cataloged using [python API](../interactions.md)


This functionality is possible in [python](../concepts/task.md/#python_functions)
and [notebook](../concepts/task.md/#notebook) tasks.

```python linenums="1" hl_lines="11 23 35 45"
--8<-- "examples/concepts/catalog_api.py"
```




## Passing Data Objects

Data objects can be shared between [python](../concepts/task.md/#python_functions) or
[notebook](../concepts/task.md/#notebook) tasks,
instead of serializing data and deserializing to file structure, using
[get_object](../interactions.md/#magnus.get_object) and [put_object](../interactions.md/#magnus.put_object).

Internally, we use [pickle](https:/docs.python.org/3/library/pickle.html) to serialize and
deserialize python objects. Please ensure that the object can be serialized via pickle.

### Example

In the below example, the step ```put_data_object``` puts a pydantic object into the catalog while the step
```retrieve_object``` retrieves the pydantic object from the catalog and prints it.

You can run this example by ```python run examples/concepts/catalog_object.py```

```python linenums="1" hl_lines="10 30 38"
--8<-- "examples/concepts/catalog_object.py"
```
