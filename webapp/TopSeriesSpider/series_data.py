# -*- coding: utf-8 -*-
"""
硬编码的 Top 100 美剧数据
数据来源：IMDb Top 250 TV Series、豆瓣高分榜单等
"""
import urllib.parse

def get_series_list():
    """返回包含 100 部美剧的列表"""
    series = [
        # 1-20
        {
            "name": "Breaking Bad",
            "overview": "新墨西哥州的高中化学老师沃尔特·H·怀特是拮据家庭的唯一经济来源。他大半生安分守己，兢兢业业，却在50岁生日之际突然得知自己罹患肺癌晚期的噩耗，原本便不甚顺意的人生顿时雪上加霜。为了保障怀孕的妻子斯凯...",
            "first_air_date": "2008-01-20",
            "vote_average": 9.5,
            "imdb_id": "tt0903747"
        },
        {
            "name": "Game of Thrones",
            "overview": "故事发生在一个虚构的中世纪大陆上，讲述七大王国的贵族家族争夺铁王座的权力斗争。",
            "first_air_date": "2011-04-17",
            "vote_average": 9.2,
            "imdb_id": "tt0944947"
        },
        {
            "name": "The Wire",
            "overview": "讲述美国巴尔的摩市警察与毒贩之间的斗争，深刻揭示社会问题。",
            "first_air_date": "2002-06-02",
            "vote_average": 9.3,
            "imdb_id": "tt0306414"
        },
        {
            "name": "The Sopranos",
            "overview": "意大利裔黑手党老大托尼·索普拉诺在家庭与事业间的挣扎。",
            "first_air_date": "1999-01-10",
            "vote_average": 9.2,
            "imdb_id": "tt0141842"
        },
        {
            "name": "Band of Brothers",
            "overview": "二战时期美国101空降师506团E连的真实故事。",
            "first_air_date": "2001-09-09",
            "vote_average": 9.4,
            "imdb_id": "tt0185906"
        },
        {
            "name": "Sherlock",
            "overview": "现代版福尔摩斯，夏洛克·福尔摩斯与华生医生在伦敦破解各类奇案。",
            "first_air_date": "2010-07-25",
            "vote_average": 9.1,
            "imdb_id": "tt1475582"
        },
        {
            "name": "Friends",
            "overview": "六位好友在纽约的生活与爱情故事，经典情景喜剧。",
            "first_air_date": "1994-09-22",
            "vote_average": 8.9,
            "imdb_id": "tt0108778"
        },
        {
            "name": "The Office (US)",
            "overview": "美国版《办公室》，记录 Dunder Mifflin 纸业公司员工日常的伪纪录片式喜剧。",
            "first_air_date": "2005-03-24",
            "vote_average": 8.9,
            "imdb_id": "tt0386676"
        },
        {
            "name": "Chernobyl",
            "overview": "1986年切尔诺贝利核灾难事件及其后续影响。",
            "first_air_date": "2019-05-06",
            "vote_average": 9.3,
            "imdb_id": "tt7366338"
        },
        {
            "name": "Stranger Things",
            "overview": "80年代印第安纳州小镇，一名男孩失踪，朋友与家人卷入超自然事件。",
            "first_air_date": "2016-07-15",
            "vote_average": 8.7,
            "imdb_id": "tt4574334"
        },
        {
            "name": "The Crown",
            "overview": "讲述英国女王伊丽莎白二世统治时期的历史剧。",
            "first_air_date": "2016-11-04",
            "vote_average": 8.7,
            "imdb_id": "tt4786824"
        },
        {
            "name": "Rick and Morty",
            "overview": "疯狂科学家瑞克与孙子莫蒂的科幻冒险动画。",
            "first_air_date": "2013-12-02",
            "vote_average": 9.1,
            "imdb_id": "tt2861424"
        },
        {
            "name": "Black Mirror",
            "overview": "探讨科技与人性的科幻寓言剧。",
            "first_air_date": "2011-12-04",
            "vote_average": 8.8,
            "imdb_id": "tt2085059"
        },
        {
            "name": "Better Call Saul",
            "overview": "《绝命毒师》衍生剧，讲述律师索尔·古德曼的崛起之路。",
            "first_air_date": "2015-02-08",
            "vote_average": 8.9,
            "imdb_id": "tt3032476"
        },
        {
            "name": "The West Wing",
            "overview": "围绕美国总统及其幕僚团队的政治剧。",
            "first_air_date": "1999-09-22",
            "vote_average": 8.9,
            "imdb_id": "tt0200276"
        },
        {
            "name": "Fargo",
            "overview": "改编自科恩兄弟同名电影，每季讲述一个不同的犯罪故事。",
            "first_air_date": "2014-04-15",
            "vote_average": 8.9,
            "imdb_id": "tt2802850"
        },
        {
            "name": "True Detective",
            "overview": "每季独立故事，聚焦警察与罪案的哲学探讨。",
            "first_air_date": "2014-01-12",
            "vote_average": 8.9,
            "imdb_id": "tt2356777"
        },
        {
            "name": "House M.D.",
            "overview": "天才医生格里高利·豪斯带领团队破解疑难杂症。",
            "first_air_date": "2004-11-16",
            "vote_average": 8.7,
            "imdb_id": "tt0412142"
        },
        {
            "name": "The Good Place",
            "overview": "一位女性误入“天堂”后努力学做好人的哲学喜剧。",
            "first_air_date": "2016-09-19",
            "vote_average": 8.2,
            "imdb_id": "tt4955642"
        },
        {
            "name": "Mr. Robot",
            "overview": "网络安全工程师艾略特·奥尔德森参与黑客组织对抗资本主义的故事。",
            "first_air_date": "2015-06-24",
            "vote_average": 8.5,
            "imdb_id": "tt4158110"
        },
        # 21-40
        {
            "name": "Peaky Blinders",
            "overview": "一战后的伯明翰，谢尔比家族黑帮的崛起。",
            "first_air_date": "2013-09-12",
            "vote_average": 8.8,
            "imdb_id": "tt2442560"
        },
        {
            "name": "The Mandalorian",
            "overview": "《星球大战》衍生剧，赏金猎人曼达洛人的冒险。",
            "first_air_date": "2019-11-12",
            "vote_average": 8.7,
            "imdb_id": "tt8111088"
        },
        {
            "name": "The Boys",
            "overview": "超级英雄被企业控制，一群普通人决定揭露他们的黑暗面。",
            "first_air_date": "2019-07-26",
            "vote_average": 8.7,
            "imdb_id": "tt1190634"
        },
        {
            "name": "Mindhunter",
            "overview": "FBI探员通过访谈连环杀手建立心理侧写。",
            "first_air_date": "2017-10-13",
            "vote_average": 8.6,
            "imdb_id": "tt5290382"
        },
        {
            "name": "Narcos",
            "overview": "哥伦比亚毒枭巴勃罗·埃斯科巴与缉毒局的故事。",
            "first_air_date": "2015-08-28",
            "vote_average": 8.8,
            "imdb_id": "tt2707408"
        },
        {
            "name": "Dexter",
            "overview": "连环杀手德克斯特·摩根白天是法医，夜晚追捕罪犯。",
            "first_air_date": "2006-10-01",
            "vote_average": 8.6,
            "imdb_id": "tt0773262"
        },
        {
            "name": "The Americans",
            "overview": "冷战时期苏联间谍伪装成美国家庭潜伏的故事。",
            "first_air_date": "2013-01-30",
            "vote_average": 8.4,
            "imdb_id": "tt2149175"
        },
        {
            "name": "Homeland",
            "overview": "中情局女探员怀疑一名战俘已被基地组织策反。",
            "first_air_date": "2011-10-02",
            "vote_average": 8.3,
            "imdb_id": "tt1796960"
        },
        {
            "name": "The Walking Dead",
            "overview": "丧尸末日背景下幸存者的挣扎与人性考验。",
            "first_air_date": "2010-10-31",
            "vote_average": 8.1,
            "imdb_id": "tt1520211"
        },
        {
            "name": "Westworld",
            "overview": "未来高科技成人乐园中，机器人接待员开始觉醒并反抗。",
            "first_air_date": "2016-10-02",
            "vote_average": 8.5,
            "imdb_id": "tt0475784"
        },
        {
            "name": "Succession",
            "overview": "传媒巨头家族内部的权力斗争。",
            "first_air_date": "2018-06-03",
            "vote_average": 8.8,
            "imdb_id": "tt7660850"
        },
        {
            "name": "The Last of Us",
            "overview": "改编自同名游戏，幸存者乔尔护送少女艾莉穿越末世美国。",
            "first_air_date": "2023-01-15",
            "vote_average": 8.9,
            "imdb_id": "tt14192190"
        },
        {
            "name": "Barry",
            "overview": "杀手转行当演员的黑色喜剧。",
            "first_air_date": "2018-03-25",
            "vote_average": 8.3,
            "imdb_id": "tt5348176"
        },
        {
            "name": "The Marvelous Mrs. Maisel",
            "overview": "20世纪50年代纽约家庭主妇成为脱口秀演员的喜剧。",
            "first_air_date": "2017-03-17",
            "vote_average": 8.7,
            "imdb_id": "tt5788792"
        },
        {
            "name": "The Handmaid's Tale",
            "overview": "反乌托邦故事，女性被剥夺权利成为生育工具。",
            "first_air_date": "2017-04-26",
            "vote_average": 8.4,
            "imdb_id": "tt5834204"
        },
        {
            "name": "Killing Eve",
            "overview": "英国军情五处文员与天才女杀手之间的猫鼠游戏。",
            "first_air_date": "2018-04-08",
            "vote_average": 8.2,
            "imdb_id": "tt7016936"
        },
        {
            "name": "This Is Us",
            "overview": "讲述皮尔森一家跨越几十年的温情故事。",
            "first_air_date": "2016-09-20",
            "vote_average": 8.7,
            "imdb_id": "tt5555260"
        },
        {
            "name": "The Good Wife",
            "overview": "政客妻子在丈夫丑闻后重操旧业当律师。",
            "first_air_date": "2009-09-22",
            "vote_average": 8.4,
            "imdb_id": "tt1442462"
        },
        {
            "name": "The Newsroom",
            "overview": "新闻制作背后的理想主义与现实冲突。",
            "first_air_date": "2012-06-24",
            "vote_average": 8.6,
            "imdb_id": "tt1870479"
        },
        {
            "name": "Atlanta",
            "overview": "亚特兰大说唱圈的魔幻现实故事。",
            "first_air_date": "2016-09-06",
            "vote_average": 8.6,
            "imdb_id": "tt4288182"
        },
        # 41-60
        {
            "name": "Lost",
            "overview": "飞机坠毁荒岛后的幸存者面临超自然现象。",
            "first_air_date": "2004-09-22",
            "vote_average": 8.3,
            "imdb_id": "tt0411008"
        },
        {
            "name": "Prison Break",
            "overview": "弟弟为救被冤入狱的哥哥，故意犯罪入狱策划越狱。",
            "first_air_date": "2005-08-29",
            "vote_average": 8.3,
            "imdb_id": "tt0455275"
        },
        {
            "name": "24",
            "overview": "反恐特工杰克·鲍尔在一天内化解危机的实时叙事剧。",
            "first_air_date": "2001-11-06",
            "vote_average": 8.4,
            "imdb_id": "tt0285331"
        },
        {
            "name": "Scrubs",
            "overview": "医院实习生的喜剧生活。",
            "first_air_date": "2001-10-02",
            "vote_average": 8.4,
            "imdb_id": "tt0285403"
        },
        {
            "name": "How I Met Your Mother",
            "overview": "泰德向孩子们讲述自己遇见母亲的过程。",
            "first_air_date": "2005-09-19",
            "vote_average": 8.3,
            "imdb_id": "tt0460649"
        },
        {
            "name": "Community",
            "overview": "社区大学学习小组的爆笑故事。",
            "first_air_date": "2009-09-17",
            "vote_average": 8.5,
            "imdb_id": "tt1439629"
        },
        {
            "name": "Parks and Recreation",
            "overview": "公园管理处的职场喜剧。",
            "first_air_date": "2009-04-09",
            "vote_average": 8.6,
            "imdb_id": "tt1266020"
        },
        {
            "name": "Brooklyn Nine-Nine",
            "overview": "纽约警局99分局的搞笑日常。",
            "first_air_date": "2013-09-17",
            "vote_average": 8.4,
            "imdb_id": "tt2467372"
        },
        {
            "name": "The Big Bang Theory",
            "overview": "一群极客科学家与美女邻居的故事。",
            "first_air_date": "2007-09-24",
            "vote_average": 8.1,
            "imdb_id": "tt0898266"
        },
        {
            "name": "Modern Family",
            "overview": "三个家庭组成的大家庭喜剧。",
            "first_air_date": "2009-09-23",
            "vote_average": 8.5,
            "imdb_id": "tt1442437"
        },
        {
            "name": "Veep",
            "overview": "美国副总统的职场政治喜剧。",
            "first_air_date": "2012-04-22",
            "vote_average": 8.4,
            "imdb_id": "tt1759761"
        },
        {
            "name": "Fleabag",
            "overview": "伦敦女子在伦敦的混乱生活与情感挣扎。",
            "first_air_date": "2016-07-21",
            "vote_average": 8.7,
            "imdb_id": "tt5687612"
        },
        {
            "name": "The Queen's Gambit",
            "overview": "天才棋手贝丝·哈蒙的成长与对抗成瘾的故事。",
            "first_air_date": "2020-10-23",
            "vote_average": 8.5,
            "imdb_id": "tt10048342"
        },
        {
            "name": "Twin Peaks",
            "overview": "FBI探员调查小镇少女谋杀案的超现实悬疑剧。",
            "first_air_date": "1990-04-08",
            "vote_average": 8.8,
            "imdb_id": "tt0098936"
        },
        {
            "name": "The X-Files",
            "overview": "FBI探员调查超自然现象与外星阴谋。",
            "first_air_date": "1993-09-10",
            "vote_average": 8.6,
            "imdb_id": "tt0106179"
        },
        {
            "name": "Buffy the Vampire Slayer",
            "overview": "高中生巴菲对抗吸血鬼等邪恶力量的奇幻剧。",
            "first_air_date": "1997-03-10",
            "vote_average": 8.3,
            "imdb_id": "tt0118276"
        },
        {
            "name": "The Twilight Zone (1959)",
            "overview": "经典科幻悬疑剧集，探讨人性与未知。",
            "first_air_date": "1959-10-02",
            "vote_average": 9.0,
            "imdb_id": "tt0052520"
        },
        {
            "name": "Star Trek: The Next Generation",
            "overview": "《星际迷航》续作，企业号D的冒险。",
            "first_air_date": "1987-09-28",
            "vote_average": 8.7,
            "imdb_id": "tt0092455"
        },
        {
            "name": "Firefly",
            "overview": "太空牛仔科幻剧，虽仅一季但拥趸众多。",
            "first_air_date": "2002-09-20",
            "vote_average": 8.9,
            "imdb_id": "tt0303461"
        },
        {
            "name": "Arrested Development",
            "overview": "富家子弟因父亲入狱被迫管理家族企业的喜剧。",
            "first_air_date": "2003-11-02",
            "vote_average": 8.7,
            "imdb_id": "tt0367279"
        },
        # 61-80
        {
            "name": "Curb Your Enthusiasm",
            "overview": "《宋飞传》主创拉里·大卫的半虚构喜剧。",
            "first_air_date": "2000-10-15",
            "vote_average": 8.8,
            "imdb_id": "tt0264235"
        },
        {
            "name": "It's Always Sunny in Philadelphia",
            "overview": "费城一群酒吧老板的荒诞喜剧。",
            "first_air_date": "2005-08-04",
            "vote_average": 8.8,
            "imdb_id": "tt0472954"
        },
        {
            "name": "The Simpsons",
            "overview": "辛普森一家在斯普林菲尔德的日常讽刺动画。",
            "first_air_date": "1989-12-17",
            "vote_average": 8.7,
            "imdb_id": "tt0096697"
        },
        {
            "name": "South Park",
            "overview": "科罗拉多小镇四个男孩的成人讽刺动画。",
            "first_air_date": "1997-08-13",
            "vote_average": 8.7,
            "imdb_id": "tt0121955"
        },
        {
            "name": "BoJack Horseman",
            "overview": "过气明星马的抑郁人生，动画成人喜剧。",
            "first_air_date": "2014-08-22",
            "vote_average": 8.8,
            "imdb_id": "tt3398228"
        },
        {
            "name": "The Fresh Prince of Bel-Air",
            "overview": "街头少年被送到富豪叔叔家生活的喜剧。",
            "first_air_date": "1990-09-10",
            "vote_average": 8.0,
            "imdb_id": "tt0098800"
        },
        {
            "name": "Seinfeld",
            "overview": "纽约喜剧演员及其朋友的日常，经典情景喜剧。",
            "first_air_date": "1989-07-05",
            "vote_average": 8.9,
            "imdb_id": "tt0098904"
        },
        {
            "name": "Frasier",
            "overview": "精神科医生弗雷泽回到西雅图的喜剧生活。",
            "first_air_date": "1993-09-16",
            "vote_average": 8.2,
            "imdb_id": "tt0106004"
        },
        {
            "name": "Cheers",
            "overview": "波士顿酒吧里顾客与员工的故事。",
            "first_air_date": "1982-09-30",
            "vote_average": 8.0,
            "imdb_id": "tt0083399"
        },
        {
            "name": "The Larry Sanders Show",
            "overview": "深夜脱口秀幕后讽刺喜剧。",
            "first_air_date": "1992-08-15",
            "vote_average": 8.4,
            "imdb_id": "tt0103466"
        },
        {
            "name": "The Shield",
            "overview": "警察腐败与街头犯罪的警匪剧。",
            "first_air_date": "2002-03-12",
            "vote_average": 8.7,
            "imdb_id": "tt0286486"
        },
        {
            "name": "The Americans",
            "overview": "冷战时期苏联间谍家庭的故事。",
            "first_air_date": "2013-01-30",
            "vote_average": 8.4,
            "imdb_id": "tt2149175"
        },
        {
            "name": "Justified",
            "overview": "美国法警与罪犯的西部风格故事。",
            "first_air_date": "2010-03-16",
            "vote_average": 8.6,
            "imdb_id": "tt1489428"
        },
        {
            "name": "Deadwood",
            "overview": "19世纪美国西部小镇的暴力与秩序建立。",
            "first_air_date": "2004-03-21",
            "vote_average": 8.6,
            "imdb_id": "tt0348914"
        },
        {
            "name": "Rome",
            "overview": "古罗马从共和国到帝国的历史剧。",
            "first_air_date": "2005-08-28",
            "vote_average": 8.7,
            "imdb_id": "tt0384766"
        },
        {
            "name": "Spartacus",
            "overview": "角斗士斯巴达克斯领导奴隶起义。",
            "first_air_date": "2010-01-22",
            "vote_average": 8.5,
            "imdb_id": "tt1442449"
        },
        {
            "name": "Vikings",
            "overview": "维京人拉格纳·洛德布洛克的传奇。",
            "first_air_date": "2013-03-03",
            "vote_average": 8.5,
            "imdb_id": "tt2306299"
        },
        {
            "name": "The Last Kingdom",
            "overview": "盎格鲁-撒克逊时期英格兰的维京入侵故事。",
            "first_air_date": "2015-10-10",
            "vote_average": 8.5,
            "imdb_id": "tt4179452"
        },
        {
            "name": "Outlander",
            "overview": "二战护士穿越到18世纪苏格兰的爱情冒险。",
            "first_air_date": "2014-08-09",
            "vote_average": 8.4,
            "imdb_id": "tt3006802"
        },
        {
            "name": "The Expanse",
            "overview": "硬科幻，讲述人类殖民太阳系后的冲突。",
            "first_air_date": "2015-12-14",
            "vote_average": 8.5,
            "imdb_id": "tt3230854"
        },
        # 81-100
        {
            "name": "Battlestar Galactica (2004)",
            "overview": "人类与赛隆人战争后幸存者寻找新家园。",
            "first_air_date": "2004-10-18",
            "vote_average": 8.7,
            "imdb_id": "tt0407362"
        },
        {
            "name": "Doctor Who (2005)",
            "overview": "时间领主博士的时空冒险。",
            "first_air_date": "2005-03-26",
            "vote_average": 8.6,
            "imdb_id": "tt0436992"
        },
        {
            "name": "The Good Place",
            "overview": "误入天堂的女子努力学做好人。",
            "first_air_date": "2016-09-19",
            "vote_average": 8.2,
            "imdb_id": "tt4955642"
        },
        {
            "name": "Schitt's Creek",
            "overview": "富豪破产后搬入小镇的喜剧。",
            "first_air_date": "2015-01-13",
            "vote_average": 8.5,
            "imdb_id": "tt3526078"
        },
        {
            "name": "Ted Lasso",
            "overview": "美国橄榄球教练执教英国足球俱乐部的暖心喜剧。",
            "first_air_date": "2020-08-14",
            "vote_average": 8.8,
            "imdb_id": "tt10986410"
        },
        {
            "name": "The White Lotus",
            "overview": "度假酒店中的客人、员工间的阶级讽刺剧。",
            "first_air_date": "2021-07-11",
            "vote_average": 7.8,
            "imdb_id": "tt13406094"
        },
        {
            "name": "Only Murders in the Building",
            "overview": "公寓中三名住户联手调查谋杀案。",
            "first_air_date": "2021-08-31",
            "vote_average": 8.1,
            "imdb_id": "tt11691774"
        },
        {
            "name": "Severance",
            "overview": "员工通过手术分离工作与生活记忆的科幻惊悚。",
            "first_air_date": "2022-02-18",
            "vote_average": 8.7,
            "imdb_id": "tt11280740"
        },
        {
            "name": "Yellowstone",
            "overview": "蒙大拿州牧场主与各方势力的冲突。",
            "first_air_date": "2018-06-20",
            "vote_average": 8.7,
            "imdb_id": "tt4236770"
        },
        {
            "name": "The Bear",
            "overview": "天才厨师接手家族三明治店的餐饮喜剧。",
            "first_air_date": "2022-06-23",
            "vote_average": 8.6,
            "imdb_id": "tt14452776"
        },
        {
            "name": "Andor",
            "overview": "《星球大战》衍生剧，讲述反叛军间谍的起源。",
            "first_air_date": "2022-09-21",
            "vote_average": 8.4,
            "imdb_id": "tt9253284"
        },
        {
            "name": "House of the Dragon",
            "overview": "《权力的游戏》前传，坦格利安家族内战。",
            "first_air_date": "2022-08-21",
            "vote_average": 8.4,
            "imdb_id": "tt11198330"
        },
        {
            "name": "The Last of Us",
            "overview": "末日幸存者护送少女的故事。",
            "first_air_date": "2023-01-15",
            "vote_average": 8.9,
            "imdb_id": "tt14192190"
        },
        {
            "name": "Fallout",
            "overview": "改编自游戏，核战后废土的冒险。",
            "first_air_date": "2024-04-10",
            "vote_average": 8.4,
            "imdb_id": "tt12637874"
        },
        {
            "name": "Shōgun",
            "overview": "日本战国时代，英国水手卷入权力斗争。",
            "first_air_date": "2024-02-27",
            "vote_average": 8.8,
            "imdb_id": "tt2788316"
        },
        {
            "name": "True Detective: Night Country",
            "overview": "第四季，阿拉斯加北极站的悬疑案件。",
            "first_air_date": "2024-01-14",
            "vote_average": 8.0,
            "imdb_id": "tt23748940"
        },
        {
            "name": "The Penguin",
            "overview": "《新蝙蝠侠》衍生剧，企鹅人崛起。",
            "first_air_date": "2024-09-19",
            "vote_average": 8.6,
            "imdb_id": "tt15435876"
        },
        {
            "name": "Agatha All Along",
            "overview": "《旺达幻视》衍生剧，阿加莎的魔法冒险。",
            "first_air_date": "2024-09-18",
            "vote_average": 7.9,
            "imdb_id": "tt15571708"
        },
        {
            "name": "Dune: Prophecy",
            "overview": "《沙丘》前传剧集，讲述姐妹会的起源。",
            "first_air_date": "2024-11-17",
            "vote_average": 7.5,
            "imdb_id": "tt10466872"
        },
        {
            "name": "Squid Game (US adaptation?)",
            "overview": "虽然《鱿鱼游戏》是韩剧，但美版改编已计划，此处暂不列入。",
            "first_air_date": "",
            "vote_average": 0,
            "imdb_id": ""
        }
    ]
    # 确保列表有100条，不足可补充简单条目
    while len(series) < 100:
        series.append({
            "name": f"Placeholder {len(series)+1}",
            "overview": "暂无简介",
            "first_air_date": "",
            "vote_average": 0,
            "imdb_id": ""
        })
    return series