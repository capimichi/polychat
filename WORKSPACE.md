# Project structure

The project is organized into the following main files and directories:

- **pir.json**: Project configuration file.
- **perplexityapi/**: Main source code directory.
  - **api.py**: Exposes the project's main APIs.
  - **client/**: Contains the client for interacting with external services (e.g. `perplexity_client.py`).
  - **container/**: Manages configuration and initialization of components (e.g. `default_container.py`).
  - **controller/**: Implements control logic, such as chat management (`chat_controller.py`).
  - **model/**: Defines the data models used by the application (`chat.py`).
  - **service/**: Contains business logic and main services (`chat_service.py`).
  - **helper/**: Utility functions and helpers, these are usually classes containing static methods.
  - **manager/**: Interfaces with databases, the filesystem and other environmental components.
  - **repository/**: Maps entities to the database.
  - **entity/**: Contains entity definitions, if present.
  - **command/**: Contains command definitions, if present.

Each subfolder contains an `__init__.py` file to make it a Python module.

# How each component fits together

The view is made from the controller or the command.

They talk ONLY with the service layer.

The service layer contains the business logic and talks to the manager/repository/client/helper layers.

Usually other layers do not talk to each other directly, but only through the service layer.

The DI is made from injector, and the default container wires everything together, from the environment variables, the project directories, the singleton instances of all classes.

Everything passes through the container.

In the view, we initialize the container and get the required services from there, so injector can handle the dependencies.

The environment variables are loaded at container initialization time from the .env file or the system environment.

We need to make an .env.example file with all the required environment variables for the project to run.