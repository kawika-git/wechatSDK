from bot.infrastructure.wexin import WechatUtils, GroupNativeApi


class ContactNativeApi:
    """
    联系人原生接口
    """
    pass


# 获取通讯录
def get_contact_list(wechat_id):
    """
    获取通讯录列表，包含好友、关注的公众号、已保存到通讯录的群聊
    :param wechat_id: 微信id
    :return: 通讯录
    """
    req = {
        "type": 29,
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata


# 批量获取用户信息
def get_user_info(wechat_id, user_ids):
    """
    批量获取用户信息
    :param wechat_id: 微信id
    :param user_ids: 用户id
    :return: 用户信息
    """
    req = {
        "type": 21,
        "userNames": user_ids
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata['data']['profiles']

# 获取用户信息 map格式
def get_group_user_info_map(wechat_id, userIdOrGroupId):
    """
    批量获取用户信息
    :param wechat_id: 微信id
    :param userIdOrGroupId: 群id
    :return: 用户信息
    """
    res = {}
    reqData = GroupNativeApi.get_group_member_detail(wechat_id, userIdOrGroupId)
    userlist = reqData["data"]["members"]
    for user in userlist:
        res[user["userName"]] = user["nickName"]

    return res

# 设置备注
def set_remark(wechat_id, user_id, remark):
    """
    设置备注
    :param wechat_id: 微信id
    :param user_id: 用户id
    :param remark: 备注
    :return: 是否成功
    """
    req = {
        "type": 10013,
        "userName": user_id,
        "remark": remark
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata["status"] == 0


# 置顶/取消置顶联系人
def set_contact_to_top(wechat_id, user_id, is_top):
    """
    置顶/取消置顶联系人
    :param wechat_id: 微信id
    :param user_id: 用户id
    :param is_top: 是否置顶
    :return: 是否成功
    """
    req = {
        "type": 10032,
        "userName": user_id,
        "isTopMost": is_top,
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata["status"] == 0


# 删除联系人
def delete_contact(wechat_id, user_id):
    """
    删除联系人
    :param wechat_id: 微信id
    :param user_id: 用户id
    :return: 是否成功
    """
    req = {
        "type": 10051,
        "userName": user_id,
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata["status"] == 0


# 通过好友申请
def accept_friend(wechat_id, encryptUserName, ticket):
    """
    通过好友申请
    :param wechat_id: 微信id
    :param encryptUserName:  申请人的encryptUserName
    :param ticket: 申请ticket
    :return: 是否成功
    """
    req = {
        "type": 10035,
        "encryptUserName": encryptUserName,
        "ticket": ticket,
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata["status"] == 0


# 添加好友（wxid）
def add_friend_by_wxid(wechat_id, wxid, mesasge=None):
    """
    通过wxid添加好友，只能添加有交集的人（以前是好友或在同一个群聊）
    :param wechat_id: 微信id
    :param wxid:  wxid
    :param content: 附加消息
    :return: 是否成功
    """
    req = {
        "type": 10034,
        "userName": wxid,
    }
    if mesasge is not None:
        req["message"] = mesasge

    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata["status"] == 0


# 添加好友
# 简要描述
# 发起好友申请。
# 您可以自定义添加方式，但尽量保持与获取v3的渠道一致，否则对方可能收到风险提示。
def add_friend(wechat_id, encryptUserName, ticket, verifyType=None, message=None, chatroomUserName=None):
    """
    发起好友申请。
    您可以自定义添加方式，但尽量保持与获取v3的渠道一致，否则对方可能收到风险提示。
    :param wechat_id:  微信id
    :param encryptUserName: 用户v3数据，添加方式为群聊时可以是 wxid
    :param ticket: 用户v4数据
    :param verifyType: 添加方式 默认为6，1：搜索QQ号，3：搜索微信号，6：朋友验证消息，14：群聊，15：搜索手机号，18：附近的人，24：摇一摇
    :param message: 验证信息
    :param chatroomUserName: 该参数仅在添加方式为群聊时生效
    :return:
    """
    req = {
        "type": 10033,
        "encryptUserName": encryptUserName,
        "ticket": ticket,
    }
    if message is not None:
        req["message"] = message
    if verifyType is not None:
        req["verifyType"] = verifyType
    if chatroomUserName is not None:
        req["chatroomUserName"] = chatroomUserName
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata["status"] == 0


# 设置用户权限
def set_user_permission(wechat_id, user_id, ):
    # todo  设置用户权限，仅聊天、不看TA、不让TA看
    req = {
        "type": 41,
        "userName": user_id,
        "contactTypes": []
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata["status"] == 0


# 关注公众号
def follow_official_account(wechat_id, bizUserName):
    """
    关注公众号
    :param wechat_id: 微信id
    :param bizUserName: 公众号wxid
    :return: 是否成功
    """
    req = {
        "type": 10036,
        "bizUserName": bizUserName,
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata["status"] == 0


# 取关公众号
def unfollow_official_account(wechat_id, bizUserName):
    return delete_contact(wechat_id, bizUserName)


# 搜索用户
def search_user(wechat_id, keyword):
    """
    微信号、手机号、QQ号查询用户信息。
    :param wechat_id: 微信id
    :param keyword: 关键词
    :return: 搜索结果
    """
    req = {
        "type": 43,
        "keyword": keyword,
    }
    resdata = WechatUtils._post_wx_request(wechat_id, req)
    return resdata

