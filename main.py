# -*- coding: utf-8 -*-
"""
校招实习监控 - 主脚本
========================
功能：每天自动爬取各大厂招聘信息，筛选符合条件的岗位，生成简洁好看的HTML日报。

架构设计（可拓展）：
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │  信息源爬虫  │ ──> │  数据清洗   │ ──> │  条件筛选   │ ──> │  HTML生成   │
  │ (spiders)   │     │ (clean)     │     │ (filter)    │     │ (generate)  │
  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │                    │
  加新源只需要          加清洗规则只          改筛选条件只          改样式只需要
  加一个函数            需要改这个            需要改config          需要改template

使用方法：
  python main.py
"""

import os
import sys
import time
import json
import logging
import requests
from datetime import datetime
from urllib.parse import urljoin
from typing import List, Dict, Optional

# 尝试导入BeautifulSoup，没有的话给出提示
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("错误：缺少依赖库 beautifulsoup4，请运行：pip install -r requirements.txt")
    sys.exit(1)

# 导入配置
import config

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================
# 数据结构：岗位信息
# ============================================================
class Job:
    """岗位信息数据类"""
    def __init__(
        self,
        company: str,
        title: str,
        city: str,
        job_type: str = "未知",
        deadline: str = "未知",
        url: str = "",
        source: str = "",
        publish_date: str = "",
    ):
        self.company = company.strip()
        self.title = title.strip()
        self.city = city.strip()
        self.job_type = job_type.strip()
        self.deadline = deadline.strip()
        self.url = url.strip()
        self.source = source.strip()
        self.publish_date = publish_date.strip()

    def to_dict(self) -> Dict:
        return {
            "company": self.company,
            "title": self.title,
            "city": self.city,
            "job_type": self.job_type,
            "deadline": self.deadline,
            "url": self.url,
            "source": self.source,
            "publish_date": self.publish_date,
        }

    def __repr__(self):
        return f"Job({self.company} - {self.title} - {self.city})"


# ============================================================
# 一、信息源爬虫模块（可拓展：加新源只需要加一个函数）
# ============================================================

def fetch_url(url: str) -> Optional[str]:
    """通用HTTP请求，带超时和异常处理"""
    try:
        logger.info(f"正在请求：{url}")
        resp = requests.get(
            url,
            headers=config.HEADERS,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        resp.encoding = resp.apparent_encoding or "utf-8"
        if resp.status_code == 200:
            time.sleep(config.REQUEST_DELAY)  # 礼貌延迟，避免被封
            return resp.text
        else:
            logger.warning(f"请求失败，状态码：{resp.status_code} - {url}")
            return None
    except Exception as e:
        logger.error(f"请求异常：{e} - {url}")
        return None


def spider_tencent() -> List[Job]:
    """
    爬虫0：腾讯招聘官方API（信息量大，2261+岗位）
    翻页获取北京/上海的岗位
    """
    jobs = []
    import time as _time

    for page in range(1, config.TENCENT_MAX_PAGES + 1):
        try:
            params = config.TENCENT_API_PARAMS.copy()
            params["pageIndex"] = page
            params["timestamp"] = int(_time.time() * 1000)

            logger.info(f"正在请求腾讯招聘API第{page}页")
            resp = requests.get(
                config.TENCENT_API_BASE,
                params=params,
                headers=config.HEADERS,
                timeout=config.REQUEST_TIMEOUT,
            )

            if resp.status_code != 200:
                logger.warning(f"腾讯招聘API请求失败，状态码：{resp.status_code}")
                break

            data = resp.json()
            if not data or data.get("Code") != 200:
                logger.warning(f"腾讯招聘API返回异常：{data}")
                break

            posts = data.get("Data", {}).get("Posts", [])
            if not posts:
                logger.info(f"腾讯招聘第{page}页无数据，停止翻页")
                break

            for post in posts:
                try:
                    title = post.get("RecruitPostName", "").strip()
                    city = post.get("LocationName", "").strip()
                    category = post.get("CategoryName", "").strip()
                    url = post.get("PostURL", "").strip()
                    publish_date = post.get("LastUpdateTime", "").strip()

                    if not title or not city:
                        continue

                    # 只保留北京/上海的岗位
                    if not any(c in city for c in config.TARGET_CITIES):
                        continue

                    jobs.append(Job(
                        company="腾讯",
                        title=title,
                        city=city,
                        job_type=category,
                        url=url,
                        source="腾讯招聘官网",
                        publish_date=publish_date,
                    ))
                except Exception as e:
                    logger.debug(f"解析腾讯招聘单个岗位失败：{e}")
                    continue

            _time.sleep(config.REQUEST_DELAY)
        except Exception as e:
            logger.error(f"腾讯招聘API请求异常：{e}")
            break

    logger.info(f"腾讯招聘爬取到 {len(jobs)} 条京沪岗位")
    return jobs


def spider_shixiseng() -> List[Job]:
    """
    爬虫0：实习僧API（可靠的结构化数据源，返回JSON）
    爬取北京/上海的实习信息
    """
    jobs = []
    for api_url in config.SHIXISENG_API_URLS:
        try:
            logger.info(f"正在请求实习僧API：{api_url}")
            resp = requests.get(
                api_url,
                headers=config.HEADERS,
                timeout=config.REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.warning(f"实习僧API请求失败，状态码：{resp.status_code}")
                continue

            data = resp.json()
            if not data or "msg" not in data:
                logger.warning("实习僧API返回数据格式异常")
                continue

            for item in data.get("msg", []):
                try:
                    company = item.get("cname", "").strip()
                    title = item.get("name", "").strip()
                    city = item.get("city", "").strip()
                    uuid = item.get("uuid", "").strip()
                    refresh_date = item.get("refresh", "").strip()
                    minsal = item.get("minsal", 0)
                    maxsal = item.get("maxsal", 0)

                    if not company or not title:
                        continue

                    # 构建职位详情页URL
                    job_url = config.SHIXISENG_JOB_URL_TEMPLATE.format(uuid=uuid) if uuid else ""

                    # 薪资信息
                    salary = ""
                    if minsal and maxsal:
                        salary = f"{minsal}-{maxsal}元/天"
                    elif minsal:
                        salary = f"{minsal}元/天起"

                    jobs.append(Job(
                        company=company,
                        title=title,
                        city=city or "未知",
                        job_type="日常实习",
                        deadline=salary or "未知",
                        url=job_url,
                        source="实习僧",
                        publish_date=refresh_date,
                    ))
                except Exception as e:
                    logger.debug(f"解析实习僧单个职位失败：{e}")
                    continue

            time.sleep(config.REQUEST_DELAY)
        except Exception as e:
            logger.error(f"实习僧API请求异常：{e}")
            continue

    logger.info(f"实习僧爬取到 {len(jobs)} 条岗位")
    return jobs


def spider_yingjiesheng() -> List[Job]:
    """
    爬虫1：应届生求职网（静态HTML，稳定可靠）
    爬取北京/上海的校招实习信息
    """
    jobs = []
    for base_url in config.YINGJIESHENG_URLS:
        html = fetch_url(base_url)
        if not html:
            continue
        try:
            soup = BeautifulSoup(html, "html.parser")
            # 应届生求职网的职位列表通常在 .jobList 或 .infoList 中
            items = soup.select(".jobList li, .infoList li, .posList li")
            if not items:
                # 尝试其他选择器
                items = soup.find_all("li", class_=lambda x: x and ("job" in x.lower() or "pos" in x.lower()))

            for item in items:
                try:
                    # 提取职位名和链接
                    title_tag = item.find("a")
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    url = title_tag.get("href", "")
                    if url and not url.startswith("http"):
                        url = urljoin(base_url, url)

                    # 提取公司名
                    company = ""
                    company_tag = item.find(class_=lambda x: x and "company" in x.lower() if x else False)
                    if company_tag:
                        company = company_tag.get_text(strip=True)
                    else:
                        # 尝试从其他位置提取
                        spans = item.find_all("span")
                        if len(spans) >= 2:
                            company = spans[1].get_text(strip=True)

                    # 提取城市
                    city = ""
                    city_tag = item.find(class_=lambda x: x and ("city" in x.lower() or "location" in x.lower() or "addr" in x.lower()) if x else False)
                    if city_tag:
                        city = city_tag.get_text(strip=True)

                    # 提取发布日期
                    publish_date = ""
                    date_tag = item.find(class_=lambda x: x and ("date" in x.lower() or "time" in x.lower()) if x else False)
                    if date_tag:
                        publish_date = date_tag.get_text(strip=True)

                    if title and company:
                        jobs.append(Job(
                            company=company,
                            title=title,
                            city=city or "未知",
                            url=url,
                            source="应届生求职网",
                            publish_date=publish_date,
                        ))
                except Exception as e:
                    logger.debug(f"解析单个职位失败：{e}")
                    continue
        except Exception as e:
            logger.error(f"解析应届生求职网页面失败：{e}")
            continue

    logger.info(f"应届生求职网爬取到 {len(jobs)} 条岗位")
    return jobs


def spider_niuke() -> List[Job]:
    """
    爬虫2：牛客网（第三方汇总，信息量大）
    注意：牛客网是JavaScript渲染的页面，requests可能拿不到完整数据。
    这里尝试用牛客网的公开API，如果失败则跳过。
    """
    jobs = []
    # 牛客网职位API（尝试）
    api_urls = [
        "https://www.nowcoder.com/jobs/recommend/fulltime?cityCode=0&jobType=0&page=1",
        "https://www.nowcoder.com/jobs/recommend/intern?cityCode=0&jobType=0&page=1",
    ]
    for url in api_urls:
        html = fetch_url(url)
        if not html:
            continue
        try:
            soup = BeautifulSoup(html, "html.parser")
            # 牛客网职位卡片
            cards = soup.select(".job-card, .recruit-list-item, .position-item")
            for card in cards:
                try:
                    title_tag = card.find("a", class_=lambda x: x and "title" in x.lower() if x else False)
                    if not title_tag:
                        title_tag = card.find("a")
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    job_url = title_tag.get("href", "")
                    if job_url and not job_url.startswith("http"):
                        job_url = urljoin("https://www.nowcoder.com", job_url)

                    company = ""
                    company_tag = card.find(class_=lambda x: x and "company" in x.lower() if x else False)
                    if company_tag:
                        company = company_tag.get_text(strip=True)

                    city = ""
                    city_tag = card.find(class_=lambda x: x and ("city" in x.lower() or "addr" in x.lower()) if x else False)
                    if city_tag:
                        city = city_tag.get_text(strip=True)

                    if title and company:
                        jobs.append(Job(
                            company=company,
                            title=title,
                            city=city or "未知",
                            url=job_url,
                            source="牛客网",
                        ))
                except Exception as e:
                    logger.debug(f"解析牛客网职位失败：{e}")
                    continue
        except Exception as e:
            logger.error(f"解析牛客网页面失败：{e}")
            continue

    logger.info(f"牛客网爬取到 {len(jobs)} 条岗位")
    return jobs


def spider_wechat_rss() -> List[Job]:
    """
    爬虫3：微信公众号RSS（第三方免费服务 feeddd.cn）
    需要在 config.py 中配置 WECHAT_RSS_URLS。
    公众号文章里的岗位信息需要从文章标题/摘要中提取。
    """
    jobs = []
    if not config.WECHAT_RSS_URLS:
        logger.info("未配置微信公众号RSS源，跳过")
        return jobs

    try:
        import feedparser
    except ImportError:
        logger.warning("缺少 feedparser 库，跳过微信RSS爬取。可运行：pip install feedparser")
        return jobs

    for rss_url in config.WECHAT_RSS_URLS:
        try:
            logger.info(f"正在解析微信RSS：{rss_url}")
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:20]:  # 每个源只取最近20篇
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")

                # 从文章标题中提取企业名（简单匹配）
                company = ""
                for comp in config.COMPANIES:
                    if comp in title or comp in summary:
                        company = comp
                        break

                if not company:
                    # 尝试从RSS源名称提取
                    company = feed.feed.get("title", "未知公众号")

                # 判断是否包含招聘相关关键词
                recruit_keywords = ["招聘", "校招", "实习", "岗位", "职位", "内推", "宣讲", "笔试", "面试"]
                if not any(kw in title for kw in recruit_keywords):
                    continue

                jobs.append(Job(
                    company=company,
                    title=title,
                    city="详见文章",
                    job_type="公众号推送",
                    url=link,
                    source="微信公众号",
                    publish_date=published,
                ))
        except Exception as e:
            logger.error(f"解析微信RSS失败：{e} - {rss_url}")
            continue

    logger.info(f"微信RSS爬取到 {len(jobs)} 条岗位")
    return jobs


def spider_official_websites() -> List[Job]:
    """
    爬虫4：大厂官网通用爬虫（预留接口，可拓展）
    每个大厂官网结构不同，需要逐个写专门的爬虫。
    第一版先留空，后续可以在这里加具体企业的官网爬虫。
    """
    jobs = []
    # 示例：添加字节跳动官网爬虫
    # jobs.extend(spider_bytedance_official())
    logger.info("官网通用爬虫（预留接口，后续可拓展）")
    return jobs


# ============================================================
# 二、数据清洗模块
# ============================================================

def clean_jobs(jobs: List[Job]) -> List[Job]:
    """数据清洗：去重、规范化"""
    seen = set()
    cleaned = []
    for job in jobs:
        # 去重键：公司+职位名+城市
        key = f"{job.company}|{job.title}|{job.city}"
        if key in seen:
            continue
        seen.add(key)

        # 规范化城市名（只保留城市名，去掉详细地址）
        for city in ["北京", "上海", "深圳", "广州", "杭州", "成都", "南京", "武汉", "西安", "苏州"]:
            if city in job.city:
                job.city = city
                break

        # 判断岗位类型
        job.job_type = classify_job_type(job.title, job.job_type)

        cleaned.append(job)

    logger.info(f"清洗后剩余 {len(cleaned)} 条岗位（去重前 {len(jobs)} 条）")
    return cleaned


def classify_job_type(title: str, default: str = "未知") -> str:
    """根据职位名判断岗位类型"""
    for job_type, keywords in config.JOB_TYPES.items():
        for kw in keywords:
            if kw in title:
                return job_type
    return default


# ============================================================
# 三、条件筛选模块
# ============================================================

def filter_jobs(jobs: List[Job]) -> List[Job]:
    """
    按条件筛选岗位：
    1. 只保留目标城市（上海/北京）
    2. 只保留目标企业（Top 30）
    3. 保留2028届可投的岗位 + 2027届校招岗位（后续分板块显示）
    """
    filtered = []
    for job in jobs:
        # 条件1：城市筛选
        if not any(city in job.city for city in config.TARGET_CITIES):
            continue

        # 条件2：企业筛选（模糊匹配，只要职位名或公司名包含目标企业名）
        matched_company = None
        for comp in config.COMPANIES:
            if comp in job.company or comp in job.title:
                matched_company = comp
                break
        if not matched_company:
            continue
        # 用匹配到的标准企业名替换
        job.company = matched_company

        # 条件3：届数筛选
        # 日常实习：全部保留（2028届可投）
        if job.job_type == "日常实习":
            filtered.append(job)
            continue

        title_lower = job.title

        # 2028届相关：保留
        is_2028 = any(kw in title_lower for kw in ["2028", "28届", "2028届"])
        if is_2028:
            filtered.append(job)
            continue

        # 2027届校招相关：保留（放到2027届板块）
        is_2027 = any(kw in title_lower for kw in config.GRAD_2027_KEYWORDS)
        if is_2027:
            filtered.append(job)
            continue

        # 没有明确届数限制的岗位：宽松保留（可能是社招或长期实习）
        has_other_grad_limit = any(
            year in title_lower for year in ["2024", "2025", "2026", "24届", "25届", "26届"]
        )
        if not has_other_grad_limit:
            filtered.append(job)

    logger.info(f"筛选后剩余 {len(filtered)} 条岗位（筛选前 {len(jobs)} 条）")
    return filtered


def classify_by_graduation(jobs: List[Job]) -> tuple:
    """
    把岗位分成两组：
    - jobs_2028：2028届可投的岗位（日常实习、暑期实习、2028届校招）- 主要部分
    - jobs_2027：2027届校招岗位 - 次要部分（参考用）
    """
    jobs_2028 = []
    jobs_2027 = []

    for job in jobs:
        title = job.title

        # 2027届校招：标题包含2027届相关关键词，且不是日常实习
        is_2027 = any(kw in title for kw in ["2027", "27届", "2027届"])
        if is_2027 and job.job_type != "日常实习":
            jobs_2027.append(job)
            continue

        # 其他都归到2028届可投（日常实习、暑期实习、无明确届数限制的岗位）
        jobs_2028.append(job)

    logger.info(f"分类完成：2028届可投 {len(jobs_2028)} 条，2027届校招 {len(jobs_2027)} 条")
    return jobs_2028, jobs_2027


# ============================================================
# 四、HTML生成模块
# ============================================================

def generate_job_cards(jobs: List[Job]) -> str:
    """生成岗位卡片HTML（按企业分组）"""
    if not jobs:
        return '<div class="empty-state"><p>暂无相关岗位</p></div>'

    # 按企业分组
    jobs_by_company = {}
    for job in jobs:
        if job.company not in jobs_by_company:
            jobs_by_company[job.company] = []
        jobs_by_company[job.company].append(job)

    # 按企业名排序
    sorted_companies = sorted(jobs_by_company.keys())

    # 生成岗位卡片HTML
    job_cards_html = ""
    for company in sorted_companies:
        company_jobs = jobs_by_company[company]
        job_cards_html += f'<div class="company-section">\n'
        job_cards_html += f'  <h2 class="company-name">{company} <span class="job-count">{len(company_jobs)}个岗位</span></h2>\n'
        job_cards_html += f'  <div class="job-list">\n'
        for job in company_jobs:
            deadline_html = f'<span class="deadline">截止：{job.deadline}</span>' if job.deadline != "未知" else ""
            publish_html = f'<span class="publish-date">发布：{job.publish_date}</span>' if job.publish_date else ""
            source_html = f'<span class="source">来源：{job.source}</span>' if job.source else ""
            url_html = f'<a href="{job.url}" target="_blank" class="apply-btn">查看详情</a>' if job.url else '<span class="apply-btn disabled">暂无链接</span>'

            job_cards_html += f'''    <div class="job-card">
      <div class="job-header">
        <span class="job-title">{job.title}</span>
        <span class="job-type tag-{job.job_type}">{job.job_type}</span>
      </div>
      <div class="job-meta">
        <span class="city">📍 {job.city}</span>
        {deadline_html}
        {publish_html}
        {source_html}
      </div>
      <div class="job-footer">
        {url_html}
      </div>
    </div>
'''
        job_cards_html += f'  </div>\n'
        job_cards_html += f'</div>\n'

    return job_cards_html


def generate_html(jobs_2028: List[Job], jobs_2027: List[Job]) -> str:
    """生成简洁好看的HTML日报（2028届可投=主要，2027届校招=次要参考）"""
    # 统计信息
    total_2028 = len(jobs_2028)
    total_2027 = len(jobs_2027)
    all_jobs = jobs_2028 + jobs_2027
    companies = set(job.company for job in all_jobs)
    cities = set(job.city for job in all_jobs)

    # 生成两个板块的岗位卡片
    jobs_2028_html = generate_job_cards(jobs_2028)
    jobs_2027_html = generate_job_cards(jobs_2027)

    # 读取HTML模板
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.TEMPLATE_PATH)
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        logger.error(f"HTML模板文件不存在：{template_path}")
        template = get_simple_template()

    # 生成统计信息HTML
    stats_html = f"""
    <div class="stats">
      <div class="stat-item"><span class="stat-number">{total_2028}</span><span class="stat-label">2028届可投</span></div>
      <div class="stat-item"><span class="stat-number">{total_2027}</span><span class="stat-label">2027届校招参考</span></div>
      <div class="stat-item"><span class="stat-number">{len(companies)}</span><span class="stat-label">覆盖企业</span></div>
    </div>
"""

    # 替换模板中的占位符
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = template.replace("{{UPDATE_TIME}}", now)
    html = html.replace("{{STATS}}", stats_html)
    html = html.replace("{{JOBS_2028}}", jobs_2028_html)
    html = html.replace("{{JOBS_2027}}", jobs_2027_html)
    html = html.replace("{{TOTAL_2028}}", str(total_2028))
    html = html.replace("{{TOTAL_2027}}", str(total_2027))

    return html


def get_simple_template() -> str:
    """降级用的简单HTML模板"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>校招实习日报</title></head>
<body>
<h1>校招实习日报 - {{UPDATE_TIME}}</h1>
{{STATS}}
{{JOB_CARDS}}
</body></html>"""


def save_html(html: str) -> str:
    """保存HTML文件"""
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.OUTPUT_HTML_PATH)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"HTML日报已保存到：{output_path}")
    return output_path


# ============================================================
# 五、主函数
# ============================================================

def main():
    """主函数： orchestrate 整个流程"""
    logger.info("=" * 60)
    logger.info("校招实习监控 - 开始运行")
    logger.info("=" * 60)

    all_jobs = []

    # 步骤1：从各个信息源爬取数据（每个源独立，失败不影响其他源）
    logger.info("\n--- 步骤1：信息爬取 ---")

    spiders = [
        ("腾讯招聘官网", spider_tencent),
        ("实习僧API", spider_shixiseng),
        ("应届生求职网", spider_yingjiesheng),
        ("牛客网", spider_niuke),
        ("微信公众号RSS", spider_wechat_rss),
        ("大厂官网（预留）", spider_official_websites),
    ]

    for source_name, spider_func in spiders:
        try:
            logger.info(f"\n正在爬取：{source_name}")
            jobs = spider_func()
            all_jobs.extend(jobs)
            logger.info(f"{source_name} 完成，获取 {len(jobs)} 条")
        except Exception as e:
            logger.error(f"{source_name} 爬取失败：{e}")
            continue  # 一个源失败不影响其他源

    logger.info(f"\n所有源共爬取到 {len(all_jobs)} 条岗位")

    # 步骤2：数据清洗（去重、规范化）
    logger.info("\n--- 步骤2：数据清洗 ---")
    cleaned_jobs = clean_jobs(all_jobs)

    # 步骤3：条件筛选（城市、企业、毕业届数）
    logger.info("\n--- 步骤3：条件筛选 ---")
    filtered_jobs = filter_jobs(cleaned_jobs)

    # 步骤3.5：按毕业届数分类（2028届可投=主要，2027届校招=次要参考）
    logger.info("\n--- 步骤3.5：按届数分类 ---")
    jobs_2028, jobs_2027 = classify_by_graduation(filtered_jobs)

    # 步骤4：生成HTML
    logger.info("\n--- 步骤4：生成HTML日报 ---")
    html = generate_html(jobs_2028, jobs_2027)
    output_path = save_html(html)

    # 完成
    logger.info("\n" + "=" * 60)
    logger.info(f"运行完成！2028届可投 {len(jobs_2028)} 条，2027届校招参考 {len(jobs_2027)} 条")
    logger.info(f"HTML日报已生成：{output_path}")
    logger.info("=" * 60)

    return output_path


if __name__ == "__main__":
    main()
