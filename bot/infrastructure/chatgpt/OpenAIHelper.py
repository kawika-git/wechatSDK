from __future__ import annotations

import datetime
import json
import logging
import os
import pilk
import httpx
import openai
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from pydub import AudioSegment

from bot.config.config_loader import ChatGptConfig
from bot.infrastructure.PluginManager import PluginManager
from bot.infrastructure.Utils import is_direct_result
from bot.infrastructure.chatgpt import OpenAIUtils
from bot.utils import IdUtils

log = logging.getLogger(__name__)

class OpenAIHelper:
    """
    ChatGPT helper class.
    """

    def __init__(self):
        """
        Initializes the OpenAI helper class with the given configuration.
        :param config: A dictionary containing the GPT configuration
        """
        if ChatGptConfig['enable'] != "true":
            return
        self.openai_client = OpenAI(timeout=600, api_key=ChatGptConfig['api_key'], http_client=httpx.Client(
            proxies=ChatGptConfig['proxy'],
            transport=httpx.HTTPTransport(local_address="0.0.0.0"),
        ), )
        self.plugin_manager = PluginManager()
        self.config = ChatGptConfig
        self.conversations: dict[int: list] = {}  # {chat_id: history}
        self.last_updated: dict[int: datetime] = {}  # {chat_id: last_update_timestamp}

    def get_conversation_stats(self, chat_id: int) -> tuple[int, int]:
        """
        获取对话中使用的信息和标记数量。
        Gets the number of messages and tokens used in the conversation.
        :param chat_id: The chat ID
        :return: A tuple containing the number of messages and tokens used
        """
        if chat_id not in self.conversations:
            self.reset_chat_history(chat_id)
        return len(self.conversations[chat_id]), OpenAIUtils.count_tokens(self.conversations[chat_id],
                                                                          self.config['model'])

    def tts(self, content: str):
        """
        转语音
        """
        fileName = str(IdUtils.generate_unique_numeric())
        if not os.path.exists("channel"):
            os.makedirs("channel")
        # 获取当前目录的绝对路径
        filePath = os.path.abspath("channel")
        speech_file_path = filePath + os.sep + fileName+ ".mp3"
        # "alloy", "echo", "fable", "onyx", "nova", "shimmer"
        response = self.openai_client.audio.speech.create(
            model="tts-1",
            voice="echo",
            input=content,
        )
        response.stream_to_file(speech_file_path)
        audio = AudioSegment.from_mp3(speech_file_path)
        # 调整采样率和编码格式
        # audio = audio.set_frame_rate(44100).set_channels(1).set_sample_width(2)
        wavPath = filePath + os.sep + fileName+".pcm"
        audio.export(wavPath, format="s16le")
        silkPath = filePath + os.sep + fileName+".silk"
        pilk.encode(wavPath, silkPath, pcm_rate=24000, tencent=True)
        return silkPath,audio.duration_seconds

    def get_chat_response(self, chat_id: int, query: str, prompt: str = None, maxCount: int = None,model: str = None) :
        """
        #
        从GPT模型获取完整响应。
        Gets a full response from the GPT model.
        :param model:
        :param maxCount:  最大文字数
        :param prompt: 辅助提示
        :param chat_id: The chat ID
        :param query: The query to send to the model
        :return: The answer from the model and the number of tokens used
        """
        plugins_used = ()
        response = self.__common_get_chat_response(chat_id, query, prompt=prompt, maxCount=maxCount,model=model)
        if self.config['enable_functions']:
            response, plugins_used = self.__handle_function_call(chat_id, response)
            if is_direct_result(response):
                content=response.choices[0].message.content.strip()
                self.__add_to_history(chat_id, role="assistant", content=content)
                return content, response.usage.total_tokens

        answer = ''

        if len(response.choices) > 1 and self.config['n_choices'] > 1:
            for index, choice in enumerate(response.choices):
                content = choice['message']['content'].strip()
                if index == 0:
                    self.__add_to_history(chat_id, role="assistant", content=content)
                answer += f'{index + 1}\u20e3\n'
                answer += content
                answer += '\n\n'
        else:
            answer = response.choices[0].message.content.strip()
            self.__add_to_history(chat_id, role="assistant", content=answer)

        show_plugins_used = len(plugins_used) > 0 and self.config['show_plugins_used']
        plugin_names = tuple(self.plugin_manager.get_plugin_source_name(plugin) for plugin in plugins_used)
        if self.config['show_usage']:
            answer += "\n\n---\n" \
                      f"💰 {str(response.usage['total_tokens'])} {OpenAIUtils.localized_text('stats_tokens')}" \
                      f" ({str(response.usage['prompt_tokens'])} {OpenAIUtils.localized_text('prompt')}," \
                      f" {str(response.usage['completion_tokens'])} {OpenAIUtils.localized_text('completion')})"
            if show_plugins_used:
                answer += f"\n🔌 {', '.join(plugin_names)}"
        elif show_plugins_used:
            answer += f"\n\n---\n🔌 {', '.join(plugin_names)}"

        return answer, response.usage.total_tokens

    def get_chat_response_stream(self, chat_id: int, query: str):
        """
        Stream response from the GPT model.
        :param chat_id: The chat ID
        :param query: The query to send to the model
        :return: The answer from the model and the number of tokens used, or 'not_finished'
        """
        plugins_used = ()
        response = self.__common_get_chat_response(chat_id, query, stream=True)
        if self.config['enable_functions']:
            response, plugins_used = self.__handle_function_call(chat_id, response, stream=True)
            if is_direct_result(response):
                yield response, '0'
                return

        answer = ''
        for item in response:
            if 'choices' not in item or len(item.choices) == 0:
                continue
            delta = item.choices[0].delta
            if 'content' in delta and delta.content is not None:
                answer += delta.content
                yield answer, 'not_finished'
        answer = answer.strip()
        self.__add_to_history(chat_id, role="assistant", content=answer)
        tokens_used = str(OpenAIUtils.count_tokens(self.conversations[chat_id], self.config['model']))

        show_plugins_used = len(plugins_used) > 0 and self.config['show_plugins_used']
        plugin_names = tuple(self.plugin_manager.get_plugin_source_name(plugin) for plugin in plugins_used)
        if self.config['show_usage']:
            answer += f"\n\n---\n💰 {tokens_used} {OpenAIUtils.localized_text('stats_tokens')}"
            if show_plugins_used:
                answer += f"\n🔌 {', '.join(plugin_names)}"
        elif show_plugins_used:
            answer += f"\n\n---\n🔌 {', '.join(plugin_names)}"

        yield answer, tokens_used

    @retry(
        reraise=True,
        retry=retry_if_exception_type(openai.RateLimitError),
        wait=wait_fixed(20),
        stop=stop_after_attempt(3)
    )
    def __common_get_chat_response(self, chat_id: int, query: str, stream=False, prompt=None, maxCount=None,model=None):

        """
        todo async
        Request a response from the GPT model.
        :param chat_id: The chat ID
        :param query: The query to send to the model
        :return: The answer from the model and the number of tokens used
        """
        model = self.config['model'] if model is None else model
        try:
            if chat_id not in self.conversations or self.__max_age_reached(chat_id):
                self.reset_chat_history(chat_id, prompt)

            self.last_updated[chat_id] = datetime.datetime.now()

            self.__add_to_history(chat_id, role="user", content=query)

            # Summarize the chat history if it's too long to avoid excessive token usage
            # token_count = OpenAIUtils.count_tokens(self.conversations[chat_id], model)
            # exceeded_max_tokens = token_count + self.config['max_tokens'] > OpenAIUtils.max_model_tokens(model)
            exceeded_max_history_size = len(self.conversations[chat_id]) > self.config['max_history_size']

            # if exceeded_max_tokens or exceeded_max_history_size:
            if exceeded_max_history_size:
                logging.info(f'Chat history for chat ID {chat_id} is too long. Summarising...')
                try:
                    summary = self.__summarise(self.conversations[chat_id][:-1])
                    logging.debug(f'Summary: {summary}')
                    self.reset_chat_history(chat_id, self.conversations[chat_id][0]['content'])
                    self.__add_to_history(chat_id, role="assistant", content=summary)
                    self.__add_to_history(chat_id, role="user", content=query)
                except Exception as e:
                    logging.warning(f'Error while summarising chat history: {str(e)}. Popping elements instead...')
                    self.conversations[chat_id] = self.conversations[chat_id][-self.config['max_history_size']:]

            common_args = {
                'model': model,
                'messages': self.conversations[chat_id],
                'temperature': self.config['temperature'],
                'n': self.config['n_choices'],
                'max_tokens': maxCount if maxCount is not None else self.config['max_tokens'],
                'presence_penalty': self.config['presence_penalty'],
                'frequency_penalty': self.config['frequency_penalty'],
                'stream': stream
            }

            if self.config['enable_functions']:
                functions = self.plugin_manager.get_functions_specs()
                if len(functions) > 0:
                    common_args['functions'] = self.plugin_manager.get_functions_specs()
                    common_args['function_call'] = 'auto'
            return self.openai_client.chat.completions.create(**common_args)
        except openai.RateLimitError as e:
            raise e
        except Exception as e:
            raise e

    def __handle_function_call(self, chat_id, response, stream=False, times=0, plugins_used=()):
        # todo async
        function_name = ''
        arguments = ''
        if stream:
            # async
            for item in response:
                if len(item.choices) > 0:
                    first_choice = item.choices[0]
                    if first_choice.delta is not None and first_choice.delta.function_call is not None:
                        if first_choice.delta.function_call.name is not None:
                            function_name += first_choice.delta.function_call.name
                        if first_choice.delta.function_call.arguments is not None:
                            arguments += str(first_choice.delta.function_call.arguments)
                    elif 'finish_reason' in first_choice and first_choice.finish_reason == 'function_call':
                        break
                    else:
                        return response, plugins_used
                else:
                    return response, plugins_used
        else:
            if len(response.choices) > 0:
                first_choice = response.choices[0]
                if first_choice.message.function_call is not None:
                    if first_choice.message.function_call.name is not None:
                        function_name += first_choice.message.function_call.name
                    if first_choice.message.function_call.arguments is not None:
                        arguments += str(first_choice.message.function_call.arguments)
                else:
                    return response, plugins_used
            else:
                return response, plugins_used

        logging.info(f'Calling function {function_name} with arguments {arguments}')
        function_response = self.plugin_manager.call_function(function_name, arguments)

        if function_name not in plugins_used:
            plugins_used += (function_name,)

        if is_direct_result(function_response):
            self.__add_function_call_to_history(chat_id=chat_id, function_name=function_name,
                                                content=json.dumps({'result': 'Done, the content has been sent'
                                                                              'to the user.'}))
            return function_response, plugins_used

        self.__add_function_call_to_history(chat_id=chat_id, function_name=function_name, content=function_response)

        chat_req = {
            "model": self.config['model'],
            "messages": self.conversations[chat_id],
            'temperature': self.config['temperature'],
            'n': self.config['n_choices'],
            'max_tokens': self.config['max_tokens'],
            'presence_penalty': self.config['presence_penalty'],
            'frequency_penalty': self.config['frequency_penalty'],
            "stream": stream,

            "functions": self.plugin_manager.get_functions_specs(),
            "function_call": 'auto' if times < self.config['functions_max_consecutive_calls'] else 'none',
        }
        response = self.openai_client.chat.completions.create(**chat_req)
        return self.__handle_function_call(chat_id, response, stream, times + 1, plugins_used)

    def generate_image(self, prompt: str, model: str, size: str, quality: str) -> str:
        """
        async
        Generates an image from the given prompt using DALL·E model.
        :param prompt: The prompt to send to the model
        :return: The image URL and the image size
        """
        response = self.openai_client.images.generate(model=model, prompt=prompt,
                                                      size=size, quality=quality,
                                                      response_format='b64_json', n=1, )

        if response is None or len(response.data) == 0:
            raise Exception(f"No response from GPT prompt:{prompt}")

        return response.data[0].b64_json

    def transcribe(self, filename):
        """
        async
        Transcribes the audio file using the Whisper model.
        """
        try:
            with open(filename, "rb") as audio:
                prompt_text = self.config['whisper_prompt']
                result = openai.Audio.atranscribe("whisper-1", audio, prompt=prompt_text)
                return result.text
        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _{OpenAIUtils.localized_text('error')}._ ⚠️\n{str(e)}") from e

    def reset_chat_history(self, chat_id, content=''):
        """
        Resets the conversation history.
        """
        if content is None or content == '':
            content = ''  # todo 辅助提示
        self.conversations[chat_id] = [{"role": "system", "content": content}]

    def __max_age_reached(self, chat_id) -> bool:
        """
        Checks if the maximum conversation age has been reached.
        :param chat_id: The chat ID
        :return: A boolean indicating whether the maximum conversation age has been reached
        """
        if chat_id not in self.last_updated:
            return False
        last_updated = self.last_updated[chat_id]
        now = datetime.datetime.now()
        max_age_minutes = self.config['max_conversation_age_minutes']
        return last_updated < now - datetime.timedelta(minutes=max_age_minutes)

    def __add_function_call_to_history(self, chat_id, function_name, content):
        """
        在对话历史记录中添加函数调用
        Adds a function call to the conversation history
        """
        self.conversations[chat_id].append({"role": "function", "name": function_name, "content": content})

    def __add_to_history(self, chat_id, role, content):
        """
        在对话历史中添加一条信息。
        Adds a message to the conversation history.
        :param chat_id: The chat ID
        :param role: The role of the message sender
        :param content: The message content
        """
        self.conversations[chat_id].append({"role": role, "content": content})

    def __summarise(self, conversation) -> str:
        """
        async
        总结对话历史。
        Summarises the conversation history.
        :param conversation: The conversation history
        :return: The summary
        """
        messages = [
            {"role": "assistant", "content": "Summarize this conversation in 700 characters or less"},
            {"role": "user", "content": str(conversation)}
        ]
        response = openai.ChatCompletion.acreate(
            model=self.config['model'],
            messages=messages,
            temperature=0.4
        )
        return response.choices[0]['message']['content']

# No longer works as of July 21st 2023, as OpenAI has removed the billing API
# def get_billing_current_month(self):
#     """Gets billed usage for current month from OpenAI API.
#
#     :return: dollar amount of usage this month
#     """
#     headers = {
#         "Authorization": f"Bearer {openai.api_key}"
#     }
#     # calculate first and last day of current month
#     today = date.today()
#     first_day = date(today.year, today.month, 1)
#     _, last_day_of_month = monthrange(today.year, today.month)
#     last_day = date(today.year, today.month, last_day_of_month)
#     params = {
#         "start_date": first_day,
#         "end_date": last_day
#     }
#     response = requests.get("https://api.openai.com/dashboard/billing/usage", headers=headers, params=params)
#     billing_data = json.loads(response.text)
#     usage_month = billing_data["total_usage"] / 100  # convert cent amount to dollars
#     return usage_month

#
# print(OpenAIHelper().get_chat_response(chat_id="wxid_9zj7q9q9q9q9q9q9q9q9q9q9q9q9", query="你好"))
