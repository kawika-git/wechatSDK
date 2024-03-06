import json
import os

from dotenv import load_dotenv

from bot.infrastructure.chatgpt import OpenAIUtils


def loadCosConfig():
    load_dotenv()
    return {
        "enable": os.environ['COS_ENABLE'],
        "secret_id": os.environ['COS_SECRET_ID'],
        "secret_key": os.environ['COS_SECRET_KEY'],
        "region": os.environ['COS_REGION'],
        "bucket": os.environ['COS_BUCKET']
    }


def loadChatGptConfig():
    load_dotenv()
    model = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')
    return {
        'enable': os.environ['OPENAI_ENABLE'],
        'api_key': os.environ['OPENAI_API_KEY'],
        # 每次响应后是否显示 OpenAI 令牌使用信息
        'show_usage': os.environ.get('SHOW_USAGE', 'false').lower() == 'true',
        # 是否流式传输响应。注意：不兼容，如果启用，则N_CHOICES高于 1
        'stream': os.environ.get('STREAM', 'false').lower() == 'false',
        'proxy': os.environ.get('OPENAI_PROXY', None),
        # 内存中保留的最大消息数，之后将汇总对话以避免过多的令牌使用
        'max_history_size': int(os.environ.get('MAX_HISTORY_SIZE', 15)),
        # 自最后一条消息以来对话应存在的最大分钟数，之后对话将被重置
        'max_conversation_age_minutes': int(os.environ.get('MAX_CONVERSATION_AGE_MINUTES', 20)),
        # 设定基调并控制助手行为的系统消息
        'assistant_prompt': os.environ.get('ASSISTANT_PROMPT',
                                           'You are a useful assistant to help facilitate the use of the microsoft api'),
        'max_tokens': int(os.environ.get('MAX_TOKENS', OpenAIUtils.default_max_tokens(model=model))),
        # 为每条输入消息生成的答案数。注意STREAM：如果启用，将其设置为大于 1 的数字将无法正常工作
        'n_choices': int(os.environ.get('N_CHOICES', 1)),
        # 0 到 2 之间的数字。较高的值将使输出更加随机
        'temperature': float(os.environ.get('TEMPERATURE', 1.0)),
        'model': model,
        # 在显示面向用户的消息之前，模型在单个响应中进行的连续函数调用的最大数量
        'functions_max_consecutive_calls': int(os.environ.get('FUNCTIONS_MAX_CONSECUTIVE_CALLS', 10)),
        # -2.0 和 2.0 之间的数字。正值根据新标记目前是否出现在文本中来对其进行惩罚
        'presence_penalty': float(os.environ.get('PRESENCE_PENALTY', 0.0)),
        # -2.0 和 2.0 之间的数字。正值根据迄今为止文本中现有的频率对新标记进行惩罚
        'frequency_penalty': float(os.environ.get('FREQUENCY_PENALTY', 0.0)),
        'bot_language': os.environ.get('BOT_LANGUAGE', 'en'),
        'show_plugins_used': os.environ.get('SHOW_PLUGINS_USED', 'false').lower() == 'true',
        # 为了提高 Whisper 转录服务的准确性，特别是对于特定名称或术语，您可以设置自定义消息。 语音转文字 - 提示
        'whisper_prompt': os.environ.get('WHISPER_PROMPT', ''),
        'plugins': os.environ.get('PLUGINS', ''),
        # 是否使用函数（又名插件）。您可以在此处阅读有关功能的更多信息
        'enable_functions': os.environ.get('ENABLE_FUNCTIONS',
                                           str(OpenAIUtils.are_functions_available(model))).lower() == 'true',

    }


def loadWechatConfig():
    # 打开并读取 JSON 文件
    try:
        with open('./env_wechat.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
    except Exception as e:
        try:
            with open('../../../env_wechat.json', 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as e:
            with open('../../env_wechat.json', 'r', encoding='utf-8') as file:
                data = json.load(file)
    return data


def getWechatConfig(keyParam):
    # 初始化返回数组，用于返回结果
    wechat_config_map = {}
    wechatData = loadWechatConfig()
    # 循环获取所有的微信配置
    for key in wechatData:
        wechat_config = wechatData[key]
        try:
            if wechat_config["enable"]:
                wechat_config_map[key] = wechat_config[keyParam]
        except KeyError:
            continue
    return wechat_config_map


def getWechatConfig_msgReplay(param):
    data = getWechatConfig(param)
    if not data:
        return {}
    result = {}

    for key in data:
        msgReplayarray = data[key]
        resultData = {}
        for item in msgReplayarray:
            resultData[item["tag"]] = item
        result[key] = resultData

    return result


# 全局配置变量


App_Run_Status = True

ChatGptConfig = loadChatGptConfig()


# 微信配置变量 拉取消息的url
WechatConfig_pullMesUrl = getWechatConfig("pullMesUrl")
# 微信配置变量 管理员变量
WechatConfig_adminWxid = getWechatConfig("managementWechatId")
# 微信配置变量 请求地址变量
WechatConfig_requestUrl = getWechatConfig("requestUrl")
# 微信配置变量 免费与AI对话的次数
WechatConfig_free_call_ai = getWechatConfig("freeCount")
# 微信配置变量 是否开启AI对话
WechatConfig_enable_gpt = getWechatConfig("enableChat")
# 微信配置变量 是否开启自动加好友
WechatConfig_enable_auto_verify = getWechatConfig("enableAutoVerify")
# 微信配置变量 回调地址变量
WechatConfig_callbackUrl = getWechatConfig("callbackUrl")
# 微信配置变量 群聊提示语
WechatConfig_chatRoomPrompt = getWechatConfig("chatRoomPrompt")
# 默认回复语
WechatConfig_defaultPrompt = getWechatConfig("defaultPrompt")
# 默认回复
WechatConfig_msgReplay = getWechatConfig_msgReplay("msgReplay")
# 微信配置变量 是否开启调试模式
WechatConfig_is_debug = getWechatConfig("debug")
# 微信配置变量 调试模式下的微信ID
WechatConfig_debugFromName = getWechatConfig("debugFromName")
# 开启了assistants api的用户
WechatConfig_assistantsUser = getWechatConfig("assistantsUser")
DOWN_FILE_PATH = os.path.abspath("channel") + os.sep

if not os.path.exists(DOWN_FILE_PATH):
    os.makedirs(DOWN_FILE_PATH)

# 发朋友圈模版
SEND_MOMENTS_TEMPLATE = """<TimelineObject>
	<id>
		<![CDATA[{momentsId}]]>
	</id>
	<username>
		<![CDATA[{wechatId}]]>
	</username>
	<createTime>
		<![CDATA[{createTime}]]>
	</createTime>
	<contentDescShowType>0</contentDescShowType>
	<contentDescScene>0</contentDescScene>
	<private>
		<![CDATA[0]]>
	</private>
	<contentDesc>
		<![CDATA[{contentDesc}]]>
	</contentDesc>
	<contentattr>
		<![CDATA[0]]>
	</contentattr>
	<sourceUserName></sourceUserName>
	<sourceNickName></sourceNickName>
	<statisticsData></statisticsData>
	<weappInfo>
		<appUserName></appUserName>
		<pagePath></pagePath>
		<version>
			<![CDATA[0]]>
		</version>
		<isHidden>0</isHidden>
		<debugMode>
			<![CDATA[0]]>
		</debugMode>
		<shareActionId></shareActionId>
		<isGame>
			<![CDATA[0]]>
		</isGame>
		<messageExtraData></messageExtraData>
		<subType>
			<![CDATA[0]]>
		</subType>
		<preloadResources></preloadResources>
	</weappInfo>
	<canvasInfoXml></canvasInfoXml>
	<ContentObject>
		<contentStyle>
			<![CDATA[{contentStyle}]]>
		</contentStyle>
		<contentSubStyle>
			<![CDATA[0]]>
		</contentSubStyle>
		<title></title>
		<description></description>
		<contentUrl></contentUrl>
		{mediaList}
	</ContentObject>
	<actionInfo>
		<appMsg>
			<mediaTagName></mediaTagName>
			<messageExt></messageExt>
			<messageAction></messageAction>
		</appMsg>
	</actionInfo>
	<appInfo>
		<id></id>
	</appInfo>
	<location poiClassifyId="" poiName="" poiAddress="" poiClassifyType="0" city=""></location>
	<publicUserName></publicUserName>
	<streamvideo>
		<streamvideourl></streamvideourl>
		<streamvideothumburl></streamvideothumburl>
		<streamvideoweburl></streamvideoweburl>
	</streamvideo>
</TimelineObject>
"""
SEND_MOMENTS_MEDIA_TEMPLATE = """    		<media>
			    <id>
			        <![CDATA[{media_id}]]>
			    </id>
			    <type>
			        <![CDATA[{media_type}]]>
			    </type>
			    <title></title>
			    <description></description>
			    <private>
			        <![CDATA[0]]>
			    </private>
			    <url type="{media_url_type}" md5="{media_url_md5}" key="{media_url_key}" token="{media_url_token}" enc_idx="{media_url_encIdx}">
			        <![CDATA[{media_url_content}]]>
			    </url>
			    <thumb type="{media_thumb_type}" key="{media_thumb_key}" token="{media_thumb_token}" enc_idx="{media_thumb_encIdx}">
			        <![CDATA[{media_thumb_content}]]>
			    </thumb>
			    <videoDuration>
			        <![CDATA[0.0]]>
			    </videoDuration>
			    <size totalSize="{media_size_totalSize}" width="{media_size_width}" height="{media_size_height}"></size>
			</media>
"""
SEND_MOMENTS_MEDIA_LIST_TEMPLATE = """		<mediaList>
    		{media_elements}
		</mediaList>
"""
