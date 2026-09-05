# -*- coding: utf-8 -*-
"""
校招实习监控 - 配置文件
========================
所有可配置项都集中在这里，后续加企业、改条件只需要改这个文件，不用动主脚本。
"""

# ============================================================
# 一、监控的企业列表（Top 30，后续可随时增减）
# ============================================================
# 格式：企业名称（用于显示和匹配）
# 注意：名称要和招聘网站上显示的一致，否则可能匹配不到
COMPANIES = [
    # ---- 你已关注的24家 ----
    "字节跳动",
    "腾讯",
    "阿里巴巴",
    "美团",
    "百度",
    "京东",
    "拼多多",
    "快手",
    "小米",
    "华为",
    "网易",
    "哔哩哔哩",
    "小红书",
    "蚂蚁集团",
    "携程",
    "联想",
    "蔚来",
    "爱奇艺",
    "搜狐",
    "新浪",
    "得物",
    "腾讯音乐",
    "腾讯CDG",
    "元气森林",
    # ---- 补充的6家（Top 30）----
    "滴滴",
    "知乎",
    "OPPO",
    "vivo",
    "荣耀",
    "理想汽车",
]

# ============================================================
# 二、筛选条件
# ============================================================

# 目标工作地点（只保留这些城市的岗位）
TARGET_CITIES = ["北京", "上海"]

# 目标毕业届数（宽松匹配：日常实习全留，暑期实习/校招看是否包含以下关键词）
# 2028届 = 2028年毕业，日常实习一般不限制毕业年份
TARGET_GRADUATION_KEYWORDS = [
    "2028",
    "28届",
    "2028届",
    "不限",
    "日常实习",
    "实习",
]

# 岗位类型关键词（用于分类显示）
JOB_TYPES = {
    "日常实习": ["日常实习", "日常", "实习"],
    "暑期实习": ["暑期实习", "暑期", "暑假实习"],
    "校招": ["校园招聘", "校招", "应届", "应届生"],
    "人才计划": ["人才计划", "管培生", "新星计划", "超星计划", "AIDU", "青云计划"],
}

# ============================================================
# 三、信息源配置
# ============================================================

# 实习僧API（可靠的结构化数据源，返回JSON）
# 格式：https://www.shixiseng.com/app/interns?city=城市&page=页码&pageSize=每页数量
SHIXISENG_API_URLS = [
    "https://www.shixiseng.com/app/interns?city=北京&page=1&pageSize=50",
    "https://www.shixiseng.com/app/interns?city=上海&page=1&pageSize=50",
]

# 实习僧职位详情页URL格式（用uuid拼接）
SHIXISENG_JOB_URL_TEMPLATE = "https://www.shixiseng.com/intern/{uuid}"

# 腾讯招聘API（官方API，返回JSON，信息量大）
# 格式：https://careers.tencent.com/tencentcareer/api/post/Query?keyword=关键词&pageIndex=页码&pageSize=每页数量&language=zh-cn&area=cn
TENCENT_API_BASE = "https://careers.tencent.com/tencentcareer/api/post/Query"
TENCENT_API_PARAMS = {
    "language": "zh-cn",
    "area": "cn",
    "pageSize": 50,
}
# 腾讯招聘翻页数量（每页50，翻10页=500个岗位，避免请求太多被封）
TENCENT_MAX_PAGES = 10

# 2027届校招关键词（用于2027届板块）
GRAD_2027_KEYWORDS = [
    "2027",
    "27届",
    "2027届",
    "校园招聘",
    "校招",
    "应届",
    "应届生",
    "毕业生",
]

# 牛客网校招信息页（第三方汇总，信息量大）
# 注意：牛客网是JavaScript渲染的页面，requests可能拿不到完整数据，后续可调试
NIUKE_URLS = [
    "https://www.nowcoder.com/recommend/campus",
]

# 应届生求职网校招信息页（静态HTML，稳定可靠）
# 注意：URL需要根据实际网站结构调整
YINGJIESHENG_URLS = [
    "https://www.yingjiesheng.com/",
]

# 微信公众号RSS源（第三方免费服务 feeddd.cn，格式：https://feeddd.org/feeds/公众号ID）
# 后续可以在这里加更多公众号的RSS源
WECHAT_RSS_URLS = [
    # 示例："https://feeddd.org/feeds/5f8a8b7e8d6c7a6f5e4d3c2b",
    # 你需要去 https://feeddd.cn 搜索公众号，获取对应的RSS链接后填到这里
]

# ============================================================
# 四、输出配置
# ============================================================

# HTML输出文件路径（相对于项目根目录）
OUTPUT_HTML_PATH = "output/index.html"

# HTML模板路径
TEMPLATE_PATH = "template.html"

# 每页显示的岗位数量（0表示不限制）
ITEMS_PER_PAGE = 0

# ============================================================
# 五、爬虫配置
# ============================================================

# 请求头（模拟浏览器，避免被反爬）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 请求超时时间（秒）
REQUEST_TIMEOUT = 15

# 每次请求间隔（秒，避免被封IP）
REQUEST_DELAY = 2

# ============================================================
# 六、日志配置
# ============================================================

# 日志级别：DEBUG / INFO / WARNING / ERROR
LOG_LEVEL = "INFO"
