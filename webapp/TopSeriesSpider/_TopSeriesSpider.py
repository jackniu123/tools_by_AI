# -*- coding: utf-8 -*-
"""
主程序入口
从本地硬编码的 Top 100 美剧列表中生成国内正版平台搜索链接
"""
import asyncio
import json
from pathlib import Path
import urllib.parse
from config_loader import cfg
from logger_setup import setup_logger
from series_data import get_series_list

script_name = Path(__file__).stem
logger = setup_logger(script_name)

def build_links(series: dict) -> list:
    name = series["name"]
    encoded_name = urllib.parse.quote(name)
    links = []

    # IMDb
    if series.get("imdb_id"):
        links.append({
            "type": "IMDb",
            "url": f"https://www.imdb.com/title/{series['imdb_id']}/",
            "description": "IMDb 剧集页面"
        })

    # 正版平台
    links.append({
        "type": "腾讯视频",
        "url": f"https://v.qq.com/x/search/?q={encoded_name}",
        "description": "腾讯视频搜索页（可能部分剧集需会员）"
    })
    links.append({
        "type": "搜狐视频",
        "url": f"https://tv.sohu.com/search/?keyword={encoded_name}",
        "description": "搜狐视频搜索页（正版授权）"
    })
    links.append({
        "type": "优酷",
        "url": f"https://so.youku.com/search_video/q_{encoded_name}",
        "description": "优酷搜索页"
    })

    # 第三方源（从配置文件读取）
    for source_name, url_template in cfg.play_sources:
        links.append({
            "type": source_name,
            "url": url_template.format(encoded_name=encoded_name),
            "description": f"{source_name} 播放页（链接可能失效，版权请自行核实）"
        })

    return links

async def main():
    logger.info("程序启动")
    series_list = get_series_list()
    logger.info(f"共加载 {len(series_list)} 部美剧")

    results = []
    for idx, series in enumerate(series_list, 1):
        logger.info(f"[{idx}/{len(series_list)}] 处理: {series['name']}")
        item = {
            "name": series["name"],
            "overview": series.get("overview", ""),
            "poster": series.get("poster", ""),
            "first_air_date": series.get("first_air_date", ""),
            "vote_average": series.get("vote_average", 0),
            "links": build_links(series)
        }
        results.append(item)

    output_file = Path(cfg.log_root) / script_name / "series_links.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"结果已保存至: {output_file}")

    print("\n" + "="*60)
    print("剧集信息及播放链接（共 {} 部）".format(len(results)))
    print("="*60)
    for idx, item in enumerate(results, 1):
        print(f"\n{idx}. {item['name']}")
        print(f"   首播: {item['first_air_date']}  评分: {item['vote_average']}")
        print("   相关链接:")
        for link in item["links"]:
            print(f"     {link['type']}: {link['url']}")

    logger.info("程序结束")

if __name__ == "__main__":
    asyncio.run(main())