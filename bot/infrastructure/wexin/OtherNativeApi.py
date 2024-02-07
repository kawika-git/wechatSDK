from bot.infrastructure.wexin import WechatUtils


class OtherNativeApi:
    """
    其他接口
    """
    pass

def set_anti_withdrawal(wechatId: object ) -> object:
    """
    开启撤回消息通知
    :param file_path: 文件路径 本地文件或者http开头的url
    :return: fileId
    """
    resdata = WechatUtils._post_wx_request(wechatId,  {
        "type": 10095,
        "bEnable": True,
    })
    return resdata

def set_lag_free_downloads(wechatId: object) -> object:
    """
    开启无延迟下载
    :param file_path: 文件路径 本地文件或者http开头的url
    :return: fileId
    """
    resdata = WechatUtils._post_wx_request(wechatId,   {
        "type": 10094,
        "bEnable": True,
    })
    return resdata
