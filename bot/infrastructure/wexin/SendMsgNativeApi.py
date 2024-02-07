import base64
import os
import uuid
from datetime import datetime

from bot.infrastructure.wexin import WechatUtils, ContactNativeApi


class SendMsgNativeApi:
    """
    发送消息原生接口
    """
    pass

# 发送文本消息
def send_text_message_base(wechat_id, userIdOrGroupId, content, atUserList=[]):
    # 如果atUserList不为空，则查找atUserList中的用户，如果找到，则在content中添加@xxx
    # if not (userIdOrGroupId.startswith("wxid_") or userIdOrGroupId.endswith("@chatroom")):
    #     raise Exception(f"userIdOrGroupId必须是群id，且长度不能超过100,{userIdOrGroupId}")
    if content is None or content == '':
        return None
    if userIdOrGroupId.endswith("@chatroom"):
        user_data_map = ContactNativeApi.get_group_user_info_map(wechat_id, userIdOrGroupId)
        content = content
        if atUserList:
            content += "\n"
            for atUser in atUserList:
                if atUser in user_data_map:
                    userName = user_data_map[atUser]
                    content += ("@" + userName + "\u2005")

    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10009,
                                            "userName": userIdOrGroupId,
                                            "msgContent": content,
                                            "atUserList": atUserList
                                        })["msgSvrID"]


def send_text_message(wechat_id, userIdOrGroupId, content):
    """
    发送文本消息
    :param wechat_id: 使用哪个微信发送
    :param userIdOrGroupId: 用户ID或者群ID
    :param content:  消息内容
    :return:
    """
    return send_text_message_base(wechat_id, userIdOrGroupId, content, [])


def send_image_message(wechat_id, userIdOrGroupId, filePath):
    """
    发送图片消息
    :param wechat_id:  使用哪个微信发送
    :param userIdOrGroupId: 用户ID或者群ID
    :param filePath: 文件路径 本地文件或者http开头的url
    :return:
    """
    filePath, md5 = WechatUtils.getFilePathAndMd5(filePath)
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10010,
                                            "userName": userIdOrGroupId,
                                            "filePath": filePath
                                        })["msgSvrID"]


def send_image_base64_message(wechat_id, userIdOrGroupId, base64Str):
    # 将base64转换为图片
    imgdata = base64.b64decode(base64Str)
    today = datetime.now().strftime('%Y-%m-%d')
    directory = f"gen_image/{today}/"
    # 如果是windows电脑
    if os.name == 'nt':
        # 创建目标目录路径
        directory = f'gen_image\\{today}\\'
    # 创建目录
    os.makedirs(directory, exist_ok=True)

    imageName = str(uuid.uuid1()) + ".png"
    full_path = os.path.abspath(os.path.join(directory, imageName))
    file = open(full_path, 'wb')
    file.write(imgdata)
    file.close()
    return send_image_message(wechat_id, userIdOrGroupId, full_path)


def send_emoji_message(wechat_id, userIdOrGroupId, filePath):
    """
    发送表情
    :param wechat_id: 使用哪个微信发送
    :param userIdOrGroupId: 用户ID或者群ID
    :param filePath: 文件路径 本地文件或者http开头的url
    :return:
    """
    if not filePath.endswith(".gif"):
        raise Exception("表情文件必须是gif格式")

    filePath, md5 = WechatUtils.getFilePathAndMd5(filePath)
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10011,
                                            "userName": userIdOrGroupId,
                                            "filePath": filePath
                                        })


def send_file_message(wechat_id, userIdOrGroupId, filePath):
    """
    发送文件
    :param wechat_id:  使用哪个微信发送
    :param userIdOrGroupId: 用户ID或者群ID
    :param filePath: 文件路径 本地文件或者http开头的url
    :return: msgSvrID
    """
    filePath, md5 = WechatUtils.getFilePathAndMd5(filePath)
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10012,
                                            "userName": userIdOrGroupId,
                                            "filePath": filePath
                                        })["msgSvrID"]


# 发送名片
def send_card_message(wechat_id, userIdOrGroupId, cardUserId):
    """
    发送名片
    :param wechat_id: 使用哪个微信发送
    :param userIdOrGroupId:  用户ID或者群ID
    :param cardUserId: 名片用户id
    :return:
    """
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10037,
                                            "userName": userIdOrGroupId,
                                            "beSharedUserName": cardUserId,
                                        })["msgSvrID"]


def send_xml_message(wechat_id, userIdOrGroupId, xml):
    """
    发送xml消息
    :param wechat_id:  使用哪个微信发送
    :param userIdOrGroupId: 用户ID或者群ID
    :param xml: xml内容
    :return:
    """
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10053,
                                            "userName": userIdOrGroupId,
                                            "msgContent": xml,
                                        })


def send_location_message(wechat_id, userIdOrGroupId, longitude, latitude, label, poiName, poiId, isFromPoiList):
    """
    发送位置消息
    :param wechat_id: 使用哪个微信发送
    :param userIdOrGroupId: 用户ID或者群ID
    :param longitude: 经度
    :param latitude: 纬度
    :param label: 位置信息
    :param poiName: poi名称
    :param poiId: poiId
    :param isFromPoiList: 是否来自poi列表
    :return:
    """
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10022,
                                            "userName": userIdOrGroupId,
                                            "longitude": longitude,
                                            "latitude": latitude,
                                            "label": label,
                                            "poiName": poiName,
                                            "poiId": poiId,
                                            "isFromPoiList": False
                                        })


# 发送语音
def send_voice_message(wechat_id, userIdOrGroupId, filePath):
    """
    发送语音
    :param wechat_id: 使用哪个微信发送
    :param userIdOrGroupId: 用户ID或者群ID
    :param filePath: 文件路径 本地文件或者http开头的url
    :return:
    """
    filePath, md5 = WechatUtils.getFilePathAndMd5(filePath)
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10014,
                                            "userName": userIdOrGroupId,
                                            "filePath": filePath
                                        })


# 拍一拍
def send_shake_message(wechat_id, userId, groupId=None):
    """
    拍一拍
    :param wechat_id:  微信id
    :param userId:  用户id
    :param groupId:  如果是群聊，则需要传入群聊id
    :return:
    """
    param = {
        "type": 57,
        "userName": userId
    }
    if groupId:
        param["chatroomUserName"] = groupId
    return WechatUtils._post_wx_request(wechat_id, param)


# 转发语音消息
def forward_voice_message(wechat_id, userIdOrGroupId, fileSize, duration, fileid, aeskey):
    """
    转发语音消息
    :param wechat_id: 微信id
    :param userIdOrGroupId: 用户id或者群id
    :param fileSize: 语音文件大小
    :param duration: 语音文件时长，单位毫秒 最大60000（即60s）
    :param fileid: 语音文件id
    :param aeskey: 语音文件aeskey
    :return:
    """
    # 如果duration 大于60000，则需要强制为60000
    duration = duration if int(duration) >= 60000 else 60000
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 6,
                                            "userName": userIdOrGroupId,
                                            "fileSize": fileSize,
                                            "duration": duration,
                                            "fileid": fileid,
                                            "aeskey": aeskey
                                        })


# 发送表情（无源）
def send_emoji_message_no_file(wechat_id, userIdOrGroupId, emojiMd5):
    """
    发送表情（无源）
    :param wechat_id: 微信id
    :param userIdOrGroupId: 用户id或者群id
    :param emojiMd5: 表情包文件md5
    :param emojiLen: 表情包文件大小
    :return:
    """
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 11,
                                            "userName": userIdOrGroupId,
                                            "emojiMd5": emojiMd5
                                        })


# 撤回消息
def revoke_message(wechat_id, userIdOrGroupId, msgId):
    """
    撤回消息
    :param wechat_id: 微信id
    :param userIdOrGroupId: 用户id或者群id
    :param msgId: 通过发送消息接口返回的msgSvrID
    :return:
    """
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 58,
                                            "userName": userIdOrGroupId,
                                            "msgSvrID": int(msgId),
                                        })["status"] == 0


# 发送引用消息
def send_quote_message(wechat_id, userIdOrGroupId, msgSvrID, content, sourceContent, sourceUserName=None):
    """
    发送引用消息
    :param wechat_id: 微信id
    :param userIdOrGroupId: 用户id或者群id
    :param sourceUserName: 源消息发送者wxid，当userName为群聊id时必须提供该字段
    :param msgSvrID: 引用的消息id
    :param content: 消息内容
    :param sourceContent: 引用的消息内容
    :return:
    """
    return WechatUtils._post_wx_request(wechat_id,
                                        {
                                            "type": 10056,
                                            "userName": userIdOrGroupId,
                                            "sourceUserName": sourceUserName,
                                            "content": content,
                                            "msgSvrID": msgSvrID,
                                            "sourceContent": sourceContent,
                                        })
