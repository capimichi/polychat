import os
import asyncio
from camoufox.async_api import AsyncCamoufox
from typing import Optional
from injector import inject
import json
from browserforge.fingerprints import Screen

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.perplexity_response import PerplexityResponse


class PerplexityClient(AbstractClient):

    @inject
    def __init__(self, session_dir: str, headless: bool = False):
        self.session_dir = session_dir
        self.storage_state_path = os.path.join(session_dir, "perplexity_state.json")
        self.headless = headless

    async def login(self):
        """
        Open browser and wait 45 seconds for manual login.
        Saves the storage state for future sessions.
        """
        async with AsyncCamoufox() as browser:
            context = await browser.new_context()
            page = await context.new_page()

            # Navigate to Perplexity
            await page.goto("https://www.perplexity.ai/")

            # Wait 45 seconds for manual login
            await asyncio.sleep(45)

            # Save storage state
            await context.storage_state(path=self.storage_state_path)

            await page.close()
            await context.close()

    async def ask(self, message: str, chat_slug: Optional[str] = None, type_input: bool = True) -> PerplexityResponse:
        """
        Ask a question to Perplexity AI and wait for the complete response.

        Args:
            message: The question/message to ask
            chat_slug: Optional chat slug to continue an existing conversation

        Returns:
            The complete response content from Perplexity
        """
        constrains = Screen(max_width=1920, max_height=1080)

        async def _attempt() -> PerplexityResponse:
            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constrains
                ) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options['storage_state'] = self.storage_state_path

                context = await browser.new_context(**context_options)
                page = await context.new_page()

                if chat_slug:
                    url = f"https://www.perplexity.ai/search/{chat_slug}"
                else:
                    url = "https://www.perplexity.ai/"

                await page.goto(url)

                if type_input:
                    await self._type_message(page, "#ask-input", message)
                else:
                    await self._paste_message(page, "#ask-input", message)

                await page.keyboard.press("Enter")

                response_content: PerplexityResponse = await self._wait_for_response(page)

                await page.close()
                await context.close()

                return response_content

        return await self._retry_async(_attempt, attempts=3)

    async def _wait_for_response(self, page) -> PerplexityResponse:
        """
        Wait for and capture the complete streamed response from Perplexity.
        Monitors requests matching the SSE endpoint and validates it with Pydantic.
        """

        response_content = ""
        response_received = asyncio.Event()

        async def handle_response(response):
            nonlocal response_content
            if "/rest/sse/perplexity_ask" in response.url:
                try:
                    # Read the complete response body
                    body = await response.body()
                    raw_content = body.decode('utf-8')

                    # Parse SSE stream to find final message
                    lines = raw_content.split('\n')

                    for i, line in enumerate(lines):
                        if "event: message" in line:
                            # Check the next line for data
                            if i + 1 < len(lines):
                                next_line = lines[i + 1]
                                if next_line.startswith("data: "):
                                    json_str = next_line[6:]  # Remove "data: " prefix
                                    try:
                                        data = json.loads(json_str)
                                        if data.get("final_sse_message") == True:
                                            response_content = json_str
                                            response_received.set()
                                            break
                                    except json.JSONDecodeError:
                                        continue
                except Exception as e:
                    print(f"Error reading response: {e}")

        # Listen for responses
        page.on("response", handle_response)

        # Wait for the response (with timeout)
        try:
            await asyncio.wait_for(response_received.wait(), timeout=120)
        except asyncio.TimeoutError:
            raise Exception("Timeout waiting for Perplexity response")

        # Validate and return the PerplexityResponse using Pydantic
        return PerplexityResponse.model_validate_json(response_content)
