import shelve
import time
import re

import httpx
from openai import OpenAI

from bot.config.config_loader import ChatGptConfig


class OpenAIAssistantsApi:

    def __init__(self):
        if ChatGptConfig['enable'] != "true":
            return
        self.openai_assistants_api_db = "openai_assistants_thread_db"
        self.openai_client = OpenAI(timeout=600, api_key=ChatGptConfig['api_key'], http_client=httpx.Client(
            proxies=ChatGptConfig['proxy'],
            transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        ), )
        pass

    # --------------------------------------------------------------
    # Upload file
    # --------------------------------------------------------------
    def upload_file(self, path):
        # Upload a file with an "assistants" purpose
        file = self.openai_client.files.create(file=open(path, "rb"), purpose="assistants")
        return file

    # --------------------------------------------------------------
    # Create assistant
    # --------------------------------------------------------------
    def create_assistant(self, name, instructions, model: str = "gpt-4-1106-preview", fileArray: list = [],
                         tools: list = []):
        """
        You currently cannot set the temperature for Assistant via the API.
        """
        assistant = self.openai_client.beta.assistants.create(
            name=name,
            instructions=instructions,
            tools=tools,
            model=model,
            file_ids=fileArray,
        )
        return assistant

    # --------------------------------------------------------------
    # Thread management
    # --------------------------------------------------------------
    def check_if_thread_exists(self, user_id, assistant_id):
        with shelve.open(self.openai_assistants_api_db) as threads_shelf:
            threads_shelf_user = threads_shelf.get(user_id, None)
            if threads_shelf_user is None:
                return None
            return threads_shelf_user.get(assistant_id, None)

    def store_thread(self, user_id, thread_id, assistant_id):
        with shelve.open(self.openai_assistants_api_db, writeback=True) as threads_shelf:
            if user_id not in threads_shelf:
                threads_shelf[user_id] = {}
            if assistant_id not in threads_shelf[user_id]:
                threads_shelf[user_id][assistant_id] = thread_id

    # --------------------------------------------------------------
    # Generate response
    # --------------------------------------------------------------
    def generate_response(self, message_body, user_id, assistant_id, name):
        # Check if there is already a thread_id for the wa_id
        thread_id = self.check_if_thread_exists(user_id, assistant_id)

        # If a thread doesn't exist, create one and store it
        if thread_id is None:
            print(f"Creating new thread for {name} with wa_id {user_id}")
            thread = self.openai_client.beta.threads.create()
            self.store_thread(user_id, thread.id, assistant_id)
            thread_id = thread.id
        # Otherwise, retrieve the existing thread
        else:
            print(f"Retrieving existing thread for {name} with wa_id {user_id}")
            thread = self.openai_client.beta.threads.retrieve(thread_id)
            thread_id = thread.id

        try:
            self.openai_client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message_body,
            )
        except Exception as e:
            if "while a run" in e.message:
                #取消任务执行
                pattern = r'run_[A-Za-z0-9]+'
                matches = re.findall(pattern, e.message)
                runId = matches[0]
                self.channel_run(thread_id, runId)
                self.openai_client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=message_body,
                )
            print(e)
        # Add message to thread


        # Run the assistant and get the new message
        new_message = self.run_assistant(thread, assistant_id)
        return new_message
    def channel_run(self, threadId, runId):
        try:
            self.openai_client.beta.threads.runs.cancel(thread_id=threadId, run_id=runId)
            return True
        except Exception as e:
            if "Cannot cancel run with status" in e.message:
                return True
            print(e)
    # --------------------------------------------------------------
    # Run assistant
    # --------------------------------------------------------------
    def run_assistant(self, thread, assistant_id):
        # Retrieve the Assistant
        # Run the assistant
        run = None
        try:
            run = self.openai_client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant_id,
            )
        except Exception as e:
            if "already has an active run" in e.message:
                print(e.message)
                #取消任务执行
                pattern = r'run_[A-Za-z0-9]+'
                matches = re.findall(pattern, e.message)
                runId = matches[0]
                self.channel_run(thread.id, runId)
                run = self.openai_client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=assistant_id,
                )
        if run is None:
            return None

        # Wait for completion
        while run.status != "completed":
            # Be nice to the API
            time.sleep(0.5)
            run = self.openai_client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run.status == 'cancelled':
                return None

        # Retrieve the Messages
        messages = self.openai_client.beta.threads.messages.list(thread_id=thread.id)
        new_message = messages.data[0].content[0].text.value
        return new_message