# OpenAIHelper.py
import hashlib
import json
import logging
import os
import time

import requests

from bot.config.config_loader import WechatConfig_requestUrl

log = logging.getLogger(__name__)


def getRequestUrl(wechatId):
    try:
        result = WechatConfig_requestUrl[wechatId]
        return result
    except Exception as e:
        log.error(f"wechat request url error, wechatId:{wechatId} exception: {e}")
        # 抛异常
        raise e


# 调用微信api
def _post_wx_request(wechatId: object, requestData: object) -> object:
    requestUrl = getRequestUrl(wechatId)
    if requestUrl is None:
        # 抛异常
        raise Exception(f"wechat request url error, wechatId:{wechatId}")
    response = requests.post(requestUrl, json=requestData)
    if response.status_code != 200:
        raise Exception(f"wechat request error, wechatId:{wechatId} response: {response}")
    try:
        return json.loads(response.text)["data"]
    except Exception as e:
        log.error(f"wechat request error, wechatId:{wechatId} response: {response} exception: {e}")
        # 抛异常
        raise e


def randomMd5(param):
    """
    md5加密
    :param param:
    :return:
    """
    return hashlib.md5(param.encode(encoding='UTF-8')).hexdigest()


def getFilePathAndMd5(file_path):
    """
    获取文件路径和md5
    :param file_path:
    :return:
    """
    # 如果当前是mac电脑，则不下载到本地，返回随机md5
    if os.name == "posix":
        # 生成随机32位字符串
        return file_path, randomMd5(str(time.time()))

    local_file_path = file_path
    if file_path.startswith("http"):
        local_file_path = download_local_file(file_path)

    if not is_local_file_path(local_file_path):
        return None

    md5 = calculate_md5(local_file_path)
    return local_file_path, md5


def calculate_md5(file_path):
    # 创建一个MD5哈希对象
    md5_hash = hashlib.md5()

    # 以二进制模式打开文件，逐块读取文件并更新哈希对象
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b""):
            md5_hash.update(chunk)

    # 返回MD5哈希值的十六进制表示
    return md5_hash.hexdigest()


def is_local_file_path(path):
    # 使用os.path模块的函数判断路径是否是绝对路径，并且路径存在
    return os.path.isabs(path) and os.path.exists(path)


def download_local_file(file_path):
    """
    下载文件到本地
    :param file_path:
    :return:
    """
    # 下载到本地
    download_directory = "C:\\Users\\Administrator\\Desktop\\3.9.5.81_x64_0.0.7\\fileupload\\"
    # 如果目录不存在，则创建目录
    if not os.path.exists(download_directory):
        os.makedirs(download_directory)

    file_name = os.path.basename(file_path)
    # 构建本地文件的完整路径
    local_path = os.path.join(download_directory, file_name)
    # 文件不存在
    if os.path.exists(local_path):
        # 重新命名文件，文件名后面加上时间戳
        file_name = f"{os.path.splitext(file_name)[0]}_{int(time.time())}{os.path.splitext(file_name)[1]}"
        # 重新构建本地文件的完整路径
        local_path = os.path.join(download_directory, file_name)

    response = requests.get(file_path)

    try:
        # 检查响应状态码
        if response.status_code == 200:
            with open(local_path, 'wb') as out_file:
                out_file.write(response.content)
            return local_path
    except Exception as e:
        # 抛出异常
        raise e


def pull_message(wechat_pull_url):
    requestData = requests.get(wechat_pull_url, timeout=2)
    if requestData.status_code != 200 or requestData is None \
            or requestData.text == '' or requestData.text is None:
        return None
    return json.loads(requestData.text)
