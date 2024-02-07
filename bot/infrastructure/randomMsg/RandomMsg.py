import logging

import requests

log = logging.getLogger(__name__)

def getRandomMsg():
    try:
        response = requests.get("https://api.7585.net.cn/yan/api.php?lx=mj")
        return response.text
    except Exception as e:
        log.error(f"RandomMsg_ERROR: {e}")
        # 抛异常
        return ""