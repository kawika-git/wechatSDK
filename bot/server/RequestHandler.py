import asyncio
import logging
import random
import threading
import time

from bot.config import config_loader
from bot.config.config_loader import WechatConfig_pullMesUrl, WechatConfig_defaultPrompt
from bot.data import DbWaitVerifyFriend
from bot.infrastructure.chatgpt.OpenAIHelper import OpenAIHelper
from bot.infrastructure.wexin import WechatUtils, MsgProcessorNativeApi, ContactNativeApi, SendMsgNativeApi
from bot.service.WechatCallbackMsgService import WechatCallbackMsgService

log = logging.getLogger(__name__)


class RequestHandler:
    def __init__(self):
        self.chatgpt_client = OpenAIHelper()
        self.wechatService = WechatCallbackMsgService()
        # 循环WechatConfig_pullMesUrl 中的所有配置，启动多个线程
        for key in WechatConfig_pullMesUrl:
            threading.Thread(target=self.poll_weixin_api, args=(WechatConfig_pullMesUrl[key],)).start()
        # 处理好友通过消息
        thread_verify_friend = threading.Thread(target=self.handle_verify_friend)
        thread_verify_friend.start()

    def handle_gpt_request(self, user_input):
        return self.chatgpt_client.get_chat_response(**user_input)

    def handle_weixin_callback(self, user_input):
        self.wechatService.handle_wechat_message(user_input)

    def poll_weixin_api(self, wechat_pull_url):
        # 循环调用微信API,获取消息
        while config_loader.App_Run_Status:
            try:
                response_data = WechatUtils.pull_message(wechat_pull_url)
                if response_data is not None:
                    # self.wechatService.handle_wechat_message(response_data)
                    asyncio.run(self.wechatService.handle_wechat_message(response_data))
            except Exception as e:
                log.error(f"Exception during API call: {e}")
            time.sleep(5)

    def init_weixin_callbackUrl(self):
        # 给所有微信设置回调地址
        MsgProcessorNativeApi.add_http_processor_forAll()

    def handle_verify_friend(self):
        autoWechat = []
        for key in config_loader.WechatConfig_enable_auto_verify:
            if config_loader.WechatConfig_enable_auto_verify[key]:
                autoWechat.append(key)
        while config_loader.App_Run_Status:
            time.sleep(random.randint(10, 15))
            # 通过好友验证
            data = DbWaitVerifyFriend.select_wait_verify_friend(autoWechat)
            # log.info("handle verify friend,size:" + str(len(data)))
            for item in data:
                id, wechatId, encryptUserName, ticket = item[0], item[1], item[2], item[3]
                ContactNativeApi.accept_friend(wechatId, encryptUserName, ticket)
                DbWaitVerifyFriend.delete_wait_verify_friend(id)
                log.info(f"accept friend {wechatId} {id}")
            for replaceItem in data:
                wechatId, content, wxid = replaceItem[1], replaceItem[4], replaceItem[5]
                if wechatId in WechatConfig_defaultPrompt:
                    SendMsgNativeApi.send_text_message_base(wechatId, wxid, WechatConfig_defaultPrompt[wechatId]["defaultReply"])
