import json
import logging
import os

from injector import Injector
from dotenv import load_dotenv

from perplexityapi.client.perplexity_client import PerplexityClient


class DefaultContainer:
    injector = None
    instance = None

    @staticmethod
    def getInstance():
        if DefaultContainer.instance is None:
            DefaultContainer.instance = DefaultContainer()
        return DefaultContainer.instance

    def __init__(self):
        self.injector = Injector()

        load_dotenv()

        self._init_environment_variables()
        self._init_directories()
        self._init_logging()
        self._init_bindings()

    def get(self, key):
        return self.injector.get(key)

    def get_var(self, key):
        return self.__dict__[key]

    def _init_directories(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.var_dir = os.path.join(self.root_dir, 'var')
        os.makedirs(self.var_dir, exist_ok=True)
        self.log_dir = os.path.join(self.var_dir, 'log')
        os.makedirs(self.log_dir, exist_ok=True)
        self.app_log_path = os.path.join(self.log_dir, 'app.log')
        self.session_dir = os.path.join(self.var_dir, 'session')
        os.makedirs(self.session_dir, exist_ok=True)

    def _init_environment_variables(self):
        self.pandoc_executable = os.environ.get('PANDOC_EXECUTABLE', 'pandoc')
        self.api_host = os.environ.get('API_HOST', '0.0.0.0')
        self.api_port = int(os.environ.get('API_PORT', '8459'))
        self.session_dir_env = os.environ.get('SESSION_DIR', 'var/session')
        self.headless = os.environ.get('HEADLESS', 'false').lower() == 'true'

    def _init_logging(self):
        logging.basicConfig(filename=self.app_log_path, level=logging.INFO, filemode='a', format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

    def _init_bindings(self):
        # Bind PerplexityClient with session_dir and headless
        perplexity_client = PerplexityClient(self.session_dir, self.headless)
        self.injector.binder.bind(PerplexityClient, to=perplexity_client)
