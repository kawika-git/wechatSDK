import logging
import random
import re
import time

import xmltodict

from bot.config import config_loader
from bot.config.config_loader import WechatConfig_chatRoomPrompt, WechatConfig_adminWxid, WechatConfig_enable_gpt, \
    WechatConfig_msgReplay, WechatConfig_is_debug, \
    WechatConfig_debugFromName, WechatConfig_free_call_ai, WechatConfig_assistantsUser
from bot.infrastructure.chatgpt.OpenAIAssistantsApi import OpenAIAssistantsApi
from bot.infrastructure.chatgpt.OpenAIHelper import OpenAIHelper
from bot.infrastructure.cos.CosManager import CosManager
from bot.infrastructure.randomMsg import RandomMsg
from bot.infrastructure.wexin import SendMsgNativeApi, GroupNativeApi, ChannelNativeApi, CdnNativeApi, MomentsNativeApi, \
    ContactNativeApi

log = logging.getLogger(__name__)


class WechatMsgHandle:

    def __init__(self):

        self.chatgpt_client = OpenAIHelper()
        self.chatgpt_Assistants_Api = OpenAIAssistantsApi()
        self.cos_client = CosManager()
        # 呼叫管理员的用户
        self.callAdminUser = {}
        # 今天用户消耗的token
        self.userToken = {}
        # 用户今天的聊天次数
        self.userChatCount = {}
        # 今天日期，当日期变化时，清空用户聊天次数
        self.today = time.strftime("%Y-%m-%d", time.localtime())
        # 准备发送的朋友圈缓存
        self.moments_msg_cache = {}
        pass

    def userCanChatAi(self, wechatId, fromWechatId, type):
        if self.today != time.strftime("%Y-%m-%d", time.localtime()):
            return True
        userKey = fromWechatId + "_" + type
        if wechatId not in self.userChatCount:
            return True
        if userKey not in self.userChatCount[wechatId]:
            return True
        maxCount = WechatConfig_free_call_ai[wechatId][type] if wechatId in WechatConfig_free_call_ai and type in \
                                                                WechatConfig_free_call_ai[wechatId] else 2
        if maxCount == -1: #-1表示无限制
            return True
        if self.userChatCount[wechatId][userKey] < maxCount:
            return True
        # todo 查询用户是否付费，如果是付费了，并且在有效期内，可继续使用
        return False

    def addUserToken(self, wechatId, fromWechatId, type, total_tokens):
        if wechatId not in self.userToken:
            self.userToken[wechatId] = {}
        if fromWechatId not in self.userToken[wechatId]:
            self.userToken[wechatId][fromWechatId] = 0
        self.userToken[wechatId][fromWechatId] += total_tokens

        if self.today != time.strftime("%Y-%m-%d", time.localtime()):
            self.today = time.strftime("%Y-%m-%d", time.localtime())
            self.userToken = {}
            self.userChatCount = {}

        userKey = fromWechatId + "_" + type
        # 增加用户今天的聊天次数
        if wechatId not in self.userChatCount:
            self.userChatCount[wechatId] = {}
        if userKey not in self.userChatCount[wechatId]:
            self.userChatCount[wechatId][userKey] = 0
        self.userChatCount[wechatId][userKey] += 1

    def handle_user_message(self, wechatId, msgId, fromWechatId, msgContent, msgXml, response_content_body):
        # 如果开启了全局assistant，则调用assistant
        assistantModel = self.checkAssistantUser(wechatId, 'globleUser')
        if assistantModel:
            self.getAssistantResponse(wechatId, fromWechatId, msgContent, assistantModel)
            return
        # 默认词库回复
        if wechatId in WechatConfig_msgReplay and msgContent in WechatConfig_msgReplay[wechatId]:
            self.handle_MsgReplay(wechatId, fromWechatId, msgContent, msgXml, response_content_body)
            return
        # 如果，呼叫了管理员，则10分钟不处理消息
        if self.callAdminUser.get(wechatId) and fromWechatId in self.callAdminUser.get(wechatId)and \
                time.time() - self.callAdminUser.get(wechatId)[fromWechatId] < 600:
            return
        # 如果对用户开启了assistant，则调用assistant
        assistantModel = self.checkAssistantUser(wechatId, fromWechatId)
        if assistantModel:
            self.getAssistantResponse(wechatId, fromWechatId, msgContent, assistantModel)
            return
        # 是debug模式，并且debug用户没在名单中，则不处理
        debugAndconnect = self.checkDebugConnect(wechatId, fromWechatId, msgContent, msgXml, response_content_body)
        if not debugAndconnect:
            return
        adminMsgFlag = self.chekAdminMsgFlag(wechatId, response_content_body)
        # 如果开启聊天功能
        self.getAiChatResponse(wechatId, fromWechatId, msgContent)
        return
    def checkDebugConnect(self, wechatId, fromWechatId, msgContent, msgXml, response_content_body):
        # 不是debug模式，返回继续
        if wechatId not in WechatConfig_is_debug or not WechatConfig_is_debug[wechatId]:
            return True
        fromName = response_content_body["talkerInfo"]["nickName"]
        if wechatId in WechatConfig_is_debug and WechatConfig_is_debug[wechatId] \
                and wechatId in WechatConfig_debugFromName and self.contains_substring(fromName,
                                                                                       WechatConfig_debugFromName[
                                                                                           wechatId]):
            return True
        return False

    def contains_substring(self, main_string, string_list):
        for s in string_list:
            if s in main_string:
                return True
        return False

    def handle_group_message(self, wechatId, msgId, fromWechatId, msgContent, msgXml, response_content_body):
        # 如果reversed1中atuserlist标签中包含自己的id，说明是@自己的消息
        send_content = msgContent.split(":\n")
        group_mes_send_user, msgContent = send_content[0], send_content[1]
        msgContent = re.sub(r'@[^\u2005]+', '', msgContent).strip()
        msgContent = re.sub(r'@[^\u2005]+ ', '', msgContent).strip()

        # 如果是管理员发的消息
        adminMsgFlag = self.chekAdminMsgFlag(wechatId, response_content_body)
        chatroomType = self.getChatRoomType(wechatId, fromWechatId)
        if chatroomType == "moments" and adminMsgFlag:
            # 如果是朋友圈消息 ,并且是管理原消息，则开始发送朋友圈
            self.push_moments_message(wechatId, "text", fromWechatId, msgContent, msgXml, response_content_body)
            return
        if chatroomType == "out_address_book":
            # 外部的群，获取通讯录
            finalMsg = ""
            extendData = self.getChatRoomExtend(wechatId, fromWechatId)
            bookList = extendData['address_book']
            for item in bookList:
                # 使用re模块进行匹配
                if re.search(item['key'], msgContent):
                    finalMsg += item['value'] + "\n"
            if finalMsg != "":
                finalMsg += "\n" + RandomMsg.getRandomMsg()
                SendMsgNativeApi.send_text_message_base(wechatId, fromWechatId, finalMsg, [group_mes_send_user])
            return

        debugAndconnect = self.checkDebugConnect(wechatId, fromWechatId, msgContent, msgXml, response_content_body)
        if not debugAndconnect:
            return

        # 开启了chat聊天 并且被@了
        if wechatId in msgXml and self.getChatRoomCanAi(wechatId, fromWechatId):
            # 调用chatgpt回复
            self.getAiChatResponse(wechatId, group_mes_send_user, msgContent,
                                   fromWechatId)

    def handle_group_image_message(self, wechatId, msgId, fromWechatId, msgContent, msgXml,
                                         response_content_body):
        send_content = msgContent.split(":\n")
        group_mes_send_user, msgContent = send_content[0], send_content[1]
        msgContent = re.sub(r'@[^\u2005]+ ', '', msgContent).strip()
        # 如果是管理员发的消息
        adminMsgFlag = self.chekAdminMsgFlag(wechatId, response_content_body)
        if self.getChatRoomType(wechatId, fromWechatId) == "moments" and adminMsgFlag:
            # 如果是朋友圈消息 ,并且是管理员消息，则准备发朋友圈
            self.push_moments_message(wechatId, "image", fromWechatId, msgContent, msgXml, response_content_body)
            return

    pass

    def getAiChatResponse(self, wechatId, userId, msgContent, groupId=None):
        if not WechatConfig_enable_gpt[wechatId]:
            return
            # 剩下的才是ChatGPT
        if msgContent == "清除记忆":
            self.chatgpt_client.reset_chat_history(userId)
            SendMsgNativeApi.send_text_message_base(wechatId, userId, "清除记忆成功")
            return
        type = "text" if not groupId else self.getChatRoomType(wechatId, groupId)
        chatId = userId if not groupId else groupId + userId

        if not self.userCanChatAi(wechatId, userId, type):
            # 用户今天的免费聊天次数已经用完回复
            if groupId:
                replaceContent = "今日免费聊天次数已用完，明天再来吧~\n\n付费解锁畅聊版本，请与群主私聊"
            else:
                replaceContent = "今日免费聊天次数已用完，明天再来吧~\n\n付费解锁畅聊版本，请直接转账\n 1天1元，1月20元"
            SendMsgNativeApi.send_text_message_base(wechatId
                                                    , groupId if groupId else userId
                                                    , replaceContent
                                                    , [userId] if groupId else [])
            return
        if type == "text":
            maxCount = None if not groupId else self.getChatRoomMaxCount(wechatId, groupId)
            initPrompt = None if not groupId else self.getChatRoomPrompt(wechatId, groupId)
            response, total_tokens = self.chatgpt_client.get_chat_response(chat_id=chatId, query=msgContent,prompt=initPrompt, maxCount=maxCount)
            # response, total_tokens = msgContent, 0
            # 调用微信发送消息接口
            SendMsgNativeApi.send_text_message_base(wechatId, groupId if groupId else userId, response, [userId] if groupId else [])
            self.addUserToken(wechatId, userId, type, total_tokens)
        if type == "gpts":
            extend=self.getChatRoomExtend(wechatId, groupId)
            response, total_tokens = self.chatgpt_client.get_chat_response(chat_id=chatId, query=msgContent,model=extend["mode"])
            # response, total_tokens = msgContent, 0
            if random.randint(0, 10) > 3:
                SendMsgNativeApi.send_text_message_base(wechatId, groupId if groupId else userId, response, [userId] if groupId else [])
            else:
                slikFilePath,duration_seconds = self.chatgpt_client.tts(response)
                if duration_seconds > 59:
                    SendMsgNativeApi.send_text_message_base(wechatId, groupId if groupId else userId, "语音超过1分钟，无法发送", [userId] if groupId else [])
                else:
                    SendMsgNativeApi.send_voice_message(wechatId, groupId if groupId else userId, slikFilePath)
            self.addUserToken(wechatId, userId, type, total_tokens)
        if type == "image":
            chatRoomGroup = self.getChatRoomConfig(wechatId, groupId)
            imageModel, imageSize, imageQuality = chatRoomGroup["image_model"], chatRoomGroup["image_size"], \
                chatRoomGroup["image_quality"]

            b64_json = self.chatgpt_client.generate_image(msgContent, imageModel, imageSize, imageQuality)
            SendMsgNativeApi.send_image_base64_message(wechatId, groupId if groupId else userId, b64_json)
            # 发送引用消息，但没找到@的方法 先文本@吧
            SendMsgNativeApi.send_text_message_base(wechatId, groupId if groupId else userId, "好咯好咯，我已经帮你处理好啦~", [userId] if groupId else [])
            self.addUserToken(wechatId, userId, type, 0)
        return

    def callAdmin(self, wechatId, fromWechatId, msgContent, msgXml, response_content_body):
        if wechatId not in self.callAdminUser:
            self.callAdminUser[wechatId] = {}
        self.callAdminUser[wechatId][fromWechatId] = time.time()
        adminwechat = WechatConfig_adminWxid[wechatId]
        fromUser = response_content_body["talkerInfo"]["nickName"]
        SendMsgNativeApi.send_text_message_base(wechatId, adminwechat, "有人找你，快去看看吧！\n" + fromUser)
        SendMsgNativeApi.send_text_message_base(wechatId, fromWechatId,
                                                "你好，我正在穿衣服！请在10分钟内完成留言！我穿好衣服会回复你~")

    def chekAdminMsgFlag(self, wechatId, response_content_body):
        fromWechatId = response_content_body["from"]
        if "@chatroom" in fromWechatId and "chatroomMemberInfo" in response_content_body:
            fromWechatId = response_content_body["chatroomMemberInfo"]["userName"]
        return WechatConfig_adminWxid[wechatId] == fromWechatId if wechatId in WechatConfig_adminWxid else False

    def getChatRoomPrompt(self, wechatId, groupId):
        if self.getChatRoomCanAi(wechatId, groupId):
            return WechatConfig_chatRoomPrompt[wechatId][groupId]["prompt"]
        return ''

    def getChatRoomType(self, wechatId, groupId):
        if self.getChatRoomCanAi(wechatId, groupId):
            return WechatConfig_chatRoomPrompt[wechatId][groupId]["type"]
        return ''

    def getChatRoomExtend(self, wechatId, groupId):
        return WechatConfig_chatRoomPrompt[wechatId][groupId]["extend"]

    def getChatRoomConfig(self, wechatId, groupId):
        if self.getChatRoomCanAi(wechatId, groupId):
            return WechatConfig_chatRoomPrompt[wechatId][groupId]
        return ''

    def getChatRoomCanAi(self, wechatId, groupId):
        return wechatId in WechatConfig_chatRoomPrompt and groupId in WechatConfig_chatRoomPrompt[wechatId]

    def getChatRoomMaxCount(self, wechatId, groupId):
        if self.getChatRoomCanAi(wechatId, groupId):
            return WechatConfig_chatRoomPrompt[wechatId][groupId]["maxCount"]
        return 100

    def handle_MsgReplay(self, wechatId, fromWechatId, msgContent, msgXml, response_content_body):
        """
        处理默认消息回复
        :param wechatId:
        :param fromWechatId:
        :param msgContent:
        :param msgXml:
        :param response_content_body:
        :return:
        """

        defaultReplaceData = WechatConfig_msgReplay[wechatId][msgContent]
        replaceType = defaultReplaceData["replaceType"]
        if replaceType == "callAdmin":
            self.callAdmin(wechatId, fromWechatId, msgContent, msgXml, response_content_body)
            return
        elif replaceType == "inviteGroup":
            groupId = defaultReplaceData["groupId"]
            GroupNativeApi.add_group_member(wechatId, groupId, fromWechatId)
            return
        pass

    def handle_channel_message(self, wechatId, msgId, fromWechatId, msgContent, msgXml, response_content_body,
                                     xml_dict):
        groupId = None
        chatType = "deWaterMark"
        if "@chatroom" in fromWechatId:
            # 如果是群，则校验群是否配置了视频号无水印，如果配置了无水印则下载并回复
            groupId = fromWechatId
            if self.getChatRoomType(wechatId, groupId) != chatType:
                # 不是去水印则不处理
                return
        # 不是群、或者配置了去水印，则下载视频并回复
        objectId = xml_dict["msg"]["appmsg"]["finderFeed"]["objectId"]
        objectNonceId = xml_dict["msg"]["appmsg"]["finderFeed"]["objectNonceId"]
        senderUserName = xml_dict["msg"]["fromusername"]

        finderUserName = xml_dict["msg"]["appmsg"]["finderFeed"]["username"]
        finderNickName = xml_dict["msg"]["appmsg"]["finderFeed"]["nickname"]
        finderDescription = xml_dict["msg"]["appmsg"]["finderFeed"]["desc"]
        if not self.userCanChatAi(wechatId, senderUserName, chatType):
            # 用户今天的免费聊天次数已经用完回复
            if groupId:
                replaceContent = "今日免费聊天次数已用完，明天再来吧~\n\n付费解锁畅聊版本，请与群主私聊"
            else:
                replaceContent = "今日免费聊天次数已用完，明天再来吧~\n\n付费解锁畅聊版本，发送：【合作】可呼叫管理员"
            SendMsgNativeApi.send_text_message_base(wechatId
                                                    , groupId if groupId else senderUserName
                                                    , replaceContent
                                                    , [senderUserName] if groupId else [])
            return

        # 如果开启了COS 则上传到COS
        if self.cos_client.checkOpen():
            try:
                SendMsgNativeApi.send_text_message_base(wechatId
                                                        , groupId if groupId else senderUserName
                                                        , "解析成功，文件较大，请耐心等待~"
                                                        , [senderUserName] if groupId else [])
                mp4FilePath, _, _ = ChannelNativeApi.download_videoFromChatRoom(wechatId, finderUserName, objectId,
                                                                                objectNonceId)
                if not mp4FilePath:
                    raise Exception("下载失败")
            except Exception as e:
                SendMsgNativeApi.send_quote_message(wechatId, fromWechatId, msgId, "下载失败，换个视频试试吧",
                                                    finderDescription, senderUserName)
                return
            try:
                cos_url = self.cos_client.put_object(mp4FilePath)
                basePrompt = ""
                if "cosDeWaterMark" in config_loader.WechatConfig_defaultPrompt[wechatId]:
                    basePrompt = config_loader.WechatConfig_defaultPrompt[wechatId]["cosDeWaterMark"]
                basePrompt += cos_url + "\n"
                basePrompt += "\n作者：" + str(finderNickName)
                basePrompt += "\n标题：" + str(finderDescription)
                SendMsgNativeApi.send_text_message_base(wechatId
                                                        , groupId if groupId else senderUserName
                                                        , basePrompt
                                                        , [senderUserName] if groupId else [])
                self.addUserToken(wechatId, senderUserName, chatType, 0)
            except Exception as e:
                SendMsgNativeApi.send_text_message_base(wechatId, fromWechatId,
                                                        "解码失败，请稍后再试，如仍失败请联系管理员")
                return
        # todo 发送视频，目前只能发文件
        # SendMsgNativeApi.send_file_message(wechatId, fromWechatId, mp4FilePath)
        pass

    def push_moments_message(self, wechatId, mesType, fromWechatId, msgContent, msgXml, response_content_body):
        if wechatId not in self.moments_msg_cache or msgContent == "清除":
            self.moments_msg_cache[wechatId] = {}
            self.moments_msg_cache[wechatId]["text"] = None
            self.moments_msg_cache[wechatId]["image"] = []
            self.moments_msg_cache[wechatId]["video"] = None

        if msgContent == "清除":
            SendMsgNativeApi.send_text_message_base(wechatId, fromWechatId, "清除成功")
            return
        if msgContent == "发送":
            text_content = self.moments_msg_cache[wechatId]["text"]
            image_array = self.moments_msg_cache[wechatId]["image"]

            MomentsNativeApi.send_moments(wechatId, text_content, image_array)
            SendMsgNativeApi.send_text_message_base(wechatId, fromWechatId, "发送成功")
            # self.moments_msg_cache[wechatId]["text"] = None
            # self.moments_msg_cache[wechatId]["image"] = []
            # self.moments_msg_cache[wechatId]["video"] = None
            return

        if mesType == "text":
            # 如果是文本消息，则更新朋友圈内容缓存
            self.moments_msg_cache[wechatId]["text"] = msgContent
            return
        if mesType == "image":
            contentXml = xmltodict.parse(msgContent)
            file_id = contentXml["msg"]["img"]["@cdnthumburl"]
            aeskey = contentXml["msg"]["img"]["@cdnthumbaeskey"]
            imgPath = CdnNativeApi.download_img_from_cdn(wechatId, file_id, aeskey)
            # 如果是图片消息，则更新朋友圈图片缓存
            self.moments_msg_cache[wechatId]["image"].append(imgPath)
            return

        pass

    def checkAssistantUser(self, wechatId, fromWechatId):
        if wechatId in WechatConfig_assistantsUser:
            if fromWechatId in WechatConfig_assistantsUser[wechatId]:
                return WechatConfig_assistantsUser[wechatId][fromWechatId]["assistants"]
        return None

    def getAssistantResponse(self, wechatId, fromWechatId, msgContent, assistantModel):
        user = ContactNativeApi.get_user_info(wechatId, [fromWechatId])[0]
        userName = user['remark'] if user['remark'] else user['nickName']
        message = self.chatgpt_Assistants_Api.generate_response(msgContent, fromWechatId, assistantModel, userName)
        SendMsgNativeApi.send_text_message_base(wechatId, fromWechatId, message)
        pass
