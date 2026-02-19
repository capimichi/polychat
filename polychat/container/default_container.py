import json
import logging
import os

from injector import Injector
from dotenv import load_dotenv

from polychat.client.chat_gpt_client import ChatGptClient
from polychat.client.kimi_client import KimiClient
from polychat.client.perplexity_client import PerplexityClient
from polychat.service.chat_gpt_service import ChatGptService
from polychat.service.kimi_service import KimiService
from polychat.service.perplexity_service import PerplexityService
from polychat.controller.kimi_controller import KimiController
from polychat.controller.chat_gpt_controller import ChatGptController
from polychat.controller.perplexity_controller import PerplexityController
from polychat.controller.deepseek_controller import DeepseekController
from polychat.mapper.client.chatgpt_chat_mapper import ChatGptChatMapper
from polychat.mapper.client.kimi_chat_mapper import KimiChatMapper
from polychat.mapper.client.perplexity_chat_mapper import PerplexityChatMapper
from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper


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
        self.headless = os.environ.get('HEADLESS', 'true').lower() == 'true'

    def _init_logging(self):
        logging.basicConfig(filename=self.app_log_path, level=logging.INFO, filemode='a', format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

    def _init_bindings(self):
        chat_to_api_mapper = ChatToApiMapper()
        self.injector.binder.bind(ChatToApiMapper, to=chat_to_api_mapper)

        # Bind PerplexityClient with session_dir and headless
        perplexity_client = PerplexityClient(self.session_dir, self.headless)
        self.injector.binder.bind(PerplexityClient, to=perplexity_client)

        # Bind PerplexityService
        perplexity_chat_mapper = PerplexityChatMapper()
        self.injector.binder.bind(PerplexityChatMapper, to=perplexity_chat_mapper)
        perplexity_service = PerplexityService(perplexity_client, perplexity_chat_mapper)
        self.injector.binder.bind(PerplexityService, to=perplexity_service)

        # Bind PerplexityController
        perplexity_controller = PerplexityController(perplexity_service, chat_to_api_mapper)
        self.injector.binder.bind(PerplexityController, to=perplexity_controller)

        # Bind ChatGptClient with same session_dir and headless
        chatgpt_client = ChatGptClient(self.session_dir, self.headless)
        self.injector.binder.bind(ChatGptClient, to=chatgpt_client)

        # Bind ChatGptService
        chatgpt_chat_mapper = ChatGptChatMapper()
        self.injector.binder.bind(ChatGptChatMapper, to=chatgpt_chat_mapper)
        chatgpt_service = ChatGptService(chatgpt_client, chatgpt_chat_mapper)
        self.injector.binder.bind(ChatGptService, to=chatgpt_service)

        # Bind ChatGptController
        chatgpt_controller = ChatGptController(chatgpt_service, chat_to_api_mapper)
        self.injector.binder.bind(ChatGptController, to=chatgpt_controller)

        # Bind KimiClient
        kimi_client = KimiClient(self.session_dir, self.headless)
        self.injector.binder.bind(KimiClient, to=kimi_client)

        # Bind KimiService
        kimi_chat_mapper = KimiChatMapper()
        self.injector.binder.bind(KimiChatMapper, to=kimi_chat_mapper)
        kimi_service = KimiService(kimi_client, kimi_chat_mapper)
        self.injector.binder.bind(KimiService, to=kimi_service)

        # Bind KimiController
        kimi_controller = KimiController(kimi_service, chat_to_api_mapper)
        self.injector.binder.bind(KimiController, to=kimi_controller)

        # Bind DeepseekController (placeholder, no dependencies)
        deepseek_controller = DeepseekController()
        self.injector.binder.bind(DeepseekController, to=deepseek_controller)
