import os
import json
import time
import hashlib
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

AIGC_API_URL = "https://aigc-api.aitoolcore.com/api/v1/images/generations"
AIGC_API_KEY = "sk-aigc-ff2029014b09dab5e86d1a22c5e1b81db6bb4e1f"
AIGC_MODEL = "qwen-image-plus"

CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "weather_images"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "image_cache.json"


def load_cache():
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load cache: {e}")
    return {}


def save_cache(cache_data):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")


def get_cache_key(city, weather_text, spot_name):
    key_str = f"{city}|{weather_text}|{spot_name}"
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

SPOT_IMAGE_MAP = {
    '故宫': 'Forbidden City imperial palace with traditional Chinese architecture',
    '长城': 'Great Wall of China winding through mountains',
    '天坛': 'Temple of Heaven circular building in Beijing',
    '颐和园': 'Summer Palace lake and pavilion in Beijing',
    '外滩': 'Shanghai Bund waterfront skyline at night',
    '东方明珠': 'Oriental Pearl Tower in Shanghai',
    '豫园': 'Yuyuan Garden classical Chinese garden',
    '迪士尼': 'Shanghai Disney Castle',
    '广州塔': 'Canton Tower in Guangzhou at sunset',
    '珠江夜游': 'Pearl River night cruise with city lights',
    '白云山': 'Baiyun Mountain lush green forest',
    '陈家祠': 'Chen Clan Ancestral Hall traditional architecture',
    '世界之窗': 'Window of the World theme park',
    '欢乐谷': 'Happy Valley amusement park',
    '大梅沙': 'Dameisha Beach golden sand ocean',
    '莲花山': 'Lianhua Mountain park with city view',
    '西湖': 'West Lake Hangzhou with willow trees and pagoda',
    '灵隐寺': 'Lingyin Temple ancient Buddhist temple',
    '雷峰塔': 'Leifeng Pagoda by West Lake',
    '宋城': 'Songcheng ancient theme park',
    '大熊猫基地': 'Giant panda in bamboo forest Chengdu',
    '宽窄巷子': 'Kuanzhai Alley traditional Sichuan architecture',
    '锦里': 'Jinli ancient street with red lanterns',
    '武侯祠': 'Wuhou Shrine memorial temple',
    '兵马俑': 'Terracotta Warriors army Xi an',
    '大雁塔': 'Giant Wild Goose Pagoda Xi an',
    '城墙': 'Xi an ancient city wall',
    '华清池': 'Huaqing Pool hot spring palace',
    '中山陵': 'Sun Yat-sen Mausoleum Nanjing',
    '夫子庙': 'Confucius Temple Nanjing',
    '明孝陵': 'Ming Xiaoling Mausoleum',
    '玄武湖': 'Xuanwu Lake Nanjing with willow trees',
    '洪崖洞': 'Hongya Cave stilted buildings Chongqing',
    '解放碑': 'Jiefangbei monument Chongqing',
    '磁器口': 'Ciqikou ancient town Chongqing',
    '长江索道': 'Yangtze River cableway Chongqing',
    '黄鹤楼': 'Yellow Crane Tower Wuhan',
    '东湖': 'East Lake Wuhan cherry blossoms',
    '户部巷': 'Hubu Alley food street Wuhan',
    '武汉大学': 'Wuhan University cherry blossoms',
    '橘子洲': 'Orange Isle Changsha',
    '岳麓山': 'Yuelu Mountain Changsha autumn leaves',
    '太平街': 'Taiping Street Changsha',
    '爱晚亭': 'Aiwan Pavilion Changsha maple leaves',
    '拙政园': 'Humble Administrator Suzhou classical garden',
    '虎丘': 'Tiger Hill Suzhou pagoda',
    '周庄': 'Zhouzhou water town ancient bridges',
    '狮子林': 'Lion Grove Garden Suzhou rockeries',
    '鼓浪屿': 'Gulangyu Island Xiamen colonial architecture',
    '南普陀': 'Nanputuo Temple Xiamen',
    '环岛路': 'Huandao Road Xiamen coastal road',
    '曾厝垵': 'Zengcuo an fishing village Xiamen',
    '栈桥': 'Zhanqiao Pier Qingdao',
    '崂山': 'Laoshan Mountain Qingdao Taoist temple',
    '八大关': 'Badaguan Qingdao European architecture',
    '金沙滩': 'Golden Beach Qingdao',
    '洱海': 'Erhai Lake Dali with mountains reflection',
    '古城': 'Dali ancient town with traditional architecture',
    '苍山': 'Cangshan Mountain Dali clouds',
    '崇圣寺': 'Three Pagodas of Chongsheng Temple Dali',
    '玉龙雪山': 'Jade Dragon Snow Mountain Lijiang',
    '泸沽湖': 'Lugu Lake crystal clear water',
    '束河古镇': 'Shuhe ancient town Lijiang',
    '亚龙湾': 'Yalong Bay Sanya tropical beach',
    '天涯海角': 'Tianya Haijiao Sanya coastal rocks',
    '南山寺': 'Nanshan Temple Sanya giant Buddha',
    '蜈支洲岛': 'Wuzhizhou Island Sanya tropical paradise',
    '碧峰峡': 'Bifengxia Ya an lush forest valley',
    '蒙顶山': 'Mengding Mountain Ya an tea plantation',
    '上里古镇': 'Shangli ancient town Ya an',
    '牛背山': 'Niubei Mountain Ya an sunrise sea of clouds',
    '乐山大佛': 'Leshan Giant Buddha carved into cliff',
    '峨眉山': 'Emei Mountain golden summit sunrise',
    '东方佛都': 'Oriental Buddha City Leshan',
    '嘉阳小火车': 'Jiayang steam train through rapeseed flowers',
    '北川地震遗址': 'Beichuan earthquake memorial site',
    '九皇山': 'Jiuhuang Mountain Mianyang',
    '李白故里': 'Li Bai hometown memorial',
    '三星堆': 'Sanxingdui bronze masks mysterious',
    '绵竹年画村': 'Mianzhuan New Year painting village',
    '白马关': 'Baima Pass ancient fortress',
    '蜀南竹海': 'Shunan Bamboo Sea Yibin',
    '兴文石海': 'Xingwen Stone Forest karst landscape',
    '李庄古镇': 'Lizhuang ancient town Yibin',
    '五粮液酒厂': 'Wuliangye liquor distillery',
    '泸州老窖': 'Luzhou Laojiao ancient cellar',
    '黄荆老林': 'Huangjing old forest primeval',
    '佛宝古镇': 'Fobao ancient town Luzhou',
    '阆中古城': 'Langzhong ancient city Nanchong',
    '朱德故里': 'Zhu De hometown memorial',
    '凌云山': 'Lingyun Mountain Nanchong',
    '八台山': 'Batai Mountain Dazhou',
    '真佛山': 'Zhenfo Mountain Dazhou temple',
    '恐龙博物馆': 'Zigong Dinosaur Museum fossils',
    '燊海井': 'Shenhai Well ancient salt well',
    '仙市古镇': 'Xianshi ancient town Zigong',
    '彩灯公园': 'Zigong Lantern Festival colorful',
    '大千园': 'Daqian Garden Neijiang',
    '隆昌石牌坊': 'Longchang stone archway',
    '广德寺': 'Guangde Temple Suining',
    '灵泉寺': 'Lingquan Temple Suining',
    '剑门关': 'Jianmen Pass narrow mountain pass',
    '皇泽寺': 'Huangze Temple Guangyuan',
    '千佛崖': 'Thousand Buddha Cliff Guangyuan',
    '光雾山': 'Guangwu Mountain Bazhong autumn foliage',
    '诺水河': 'Nuoshui River Bazhong',
    '三苏祠': 'San Su Shrine Meishan',
    '瓦屋山': 'Wawu Mountain Meishan',
    '柳江古镇': 'Liujiang ancient town Meishan',
    '安岳石刻': 'Anyue stone carvings Ziyang',
    '陈毅故里': 'Chen Yi hometown memorial',
    '二滩国家森林公园': 'Ertan National Forest Park',
    '格萨拉': 'Gesalra Panzhihua plateau',
    '红格温泉': 'Hongge Hot Spring Panzhihua',
    '黔灵山': 'Qianling Mountain Guiyang',
    '甲秀楼': 'Jiaxiu Pavilion Guiyang',
    '青岩古镇': 'Qingyan ancient town Guiyang',
    '滇池': 'Dianchi Lake Kunming seagulls',
    '石林': 'Stone Forest Kunming karst pillars',
    '翠湖': 'Green Lake Kunming lotus flowers',
    '布达拉宫': 'Potala Palace Lhasa Tibet',
    '大昭寺': 'Jokhang Temple Lhasa',
    '八廓街': 'Barkhor Street Lhasa',
    '纳木错': 'Namtso Lake Tibet sacred lake',
    '塔尔寺': 'Kumbum Monastery Xining',
    '青海湖': 'Qinghai Lake rapeseed flowers',
    '西夏王陵': 'Western Xia Imperial Tombs Yinchuan',
    '沙湖': 'Sand Lake Yinchuan desert oasis',
    '天山天池': 'Heavenly Lake Urumqi Tianshan',
    '大巴扎': 'Grand Bazaar Urumqi',
    '大召寺': 'Dazhao Temple Hohhot',
    '昭君墓': 'Zhaojun Tomb Hohhot',
    '黄河铁桥': 'Yellow River Iron Bridge Lanzhou',
    '白塔山': 'White Pagoda Mountain Lanzhou',
    '晋祠': 'Jin Ci Temple Taiyuan',
    '平遥古城': 'Pingyao ancient city wall',
    '赵州桥': 'Zhaozhou Bridge ancient stone arch',
    '正定古城': 'Zhengding ancient city',
    '趵突泉': 'Baotu Spring Jinan',
    '大明湖': 'Daming Lake Jinan',
    '少林寺': 'Shaolin Temple Dengfeng',
    '龙门石窟': 'Longmen Grottoes Luoyang',
    '三河古镇': 'Sanhe ancient town Hefei',
    '滕王阁': 'Tengwang Pavilion Nanchang',
    '三坊七巷': 'Sanfang Qixiang Fuzhou',
    '青秀山': 'Qingxiu Mountain Nanning',
    '德天瀑布': 'Detian Waterfall Nanning',
    '中央大街': 'Central Street Harbin European architecture',
    '圣索菲亚教堂': 'Saint Sophia Cathedral Harbin',
    '冰雪大世界': 'Ice and Snow World Harbin',
    '伪满皇宫': 'Museum of Imperial Palace Manchukuo',
    '净月潭': 'Jingyue Pool Changchun',
    '星海广场': 'Xinghai Square Dalian',
    '老虎滩': 'Tiger Beach Dalian',
    '古文化街': 'Ancient Culture Street Tianjin',
    '五大道': 'Five Great Avenues Tianjin',
    '天一阁': 'Tianyi Pavilion Ningbo',
    '雁荡山': 'Yandang Mountain Wenzhou',
    '南湖': 'South Lake Jiaxing',
    '乌镇': 'Wuzhen water town ancient bridges',
    '西塘': 'Xitang water town',
    '鲁迅故里': 'Lu Xun Hometown Shaoxing',
    '鼋头渚': 'Yuantouzhu Wuxi cherry blossoms',
    '灵山大佛': 'Lingshan Giant Buddha Wuxi',
    '恐龙园': 'China Dinosaur Park Changzhou',
    '天宁寺': 'Tianning Temple Changzhou',
    '云龙湖': 'Yunlong Lake Xuzhou',
    '瘦西湖': 'Slender West Lake Yangzhou',
    '个园': 'Geyuan Garden Yangzhou bamboo',
    '金山寺': 'Jinshan Temple Zhenjiang',
    '双龙洞': 'Double Dragon Cave Jinhua',
    '横店影视城': 'Hengdian World Studios',
    '天台山': 'Tiantai Mountain Taizhou',
    '漓江': 'Li River Guilin karst mountains',
    '象鼻山': 'Elephant Trunk Hill Guilin',
    '阳朔': 'Yangshuo Guilin countryside',
    '龙脊梯田': 'Longji Rice Terraces',
    '武陵源': 'Wulingyuan Zhangjiajie quartzite pillars',
    '天门山': 'Tianmen Mountain Zhangjiajie glass bridge',
    '凤凰古城': 'Fenghuang ancient town Xiangxi',
    '黄山': 'Huangshan Mountain pine trees clouds',
    '宏村': 'Hongcun ancient village Anhui',
    '南靖土楼': 'Nanjing Tulou Fujian round earth building',
    '庐山': 'Lushan Mountain Jiujiang',
    '古窑民俗博览区': 'Jingdezhen ancient kiln porcelain',
    '白马寺': 'White Horse Temple Luoyang',
    '清明上河园': 'Qingming Riverside Garden Kaifeng',
    '殷墟': 'Yinxu Anyang oracle bones',
    '红旗渠': 'Red Flag Canal Anyang',
    '三峡大坝': 'Three Gorges Dam Yichang',
    '三峡人家': 'Three Gorges families Yichang',
    '古隆中': 'Gulongzhong Xiangyang',
    '武当山': 'Wudang Mountain Taoist temple',
    '恩施大峡谷': 'Enshi Grand Canyon',
    '遵义会议会址': 'Zunyi Conference Site',
    '赤水丹霞': 'Chishui Danxia landform',
}

WEATHER_CONDITIONS = {
    '晴': 'sunny bright clear blue sky golden sunlight warm glow vibrant colors',
    '多云': 'partly cloudy soft white clouds scattered across blue sky gentle diffused light',
    '阴': 'overcast cloudy gray sky soft muted lighting calm atmosphere',
    '小雨': 'light rain gentle drizzle misty atmosphere wet surfaces raindrops visible',
    '中雨': 'moderate rain steady rainfall wet streets puddles rain streaks',
    '大雨': 'heavy rain storm dramatic dark clouds pouring rain water splashes',
    '暴雨': 'torrential rain severe storm dramatic lightning dark ominous clouds flooding',
    '雷': 'thunderstorm dramatic lightning bolts dark storm clouds electric atmosphere',
    '雪': 'snow winter snowflakes falling snow covered landscape white blanket frost',
    '雾': 'fog misty mysterious atmosphere low visibility ethereal soft light',
    '霾': 'hazy smog gray atmosphere reduced visibility muted colors',
    '风': 'windy blowing clouds dramatic sky swaying trees dynamic movement',
}


def generate_weather_image_prompt(city, spot_name, weather_text):
    weather_desc = ''
    for key, desc in WEATHER_CONDITIONS.items():
        if key in weather_text:
            weather_desc = desc
            break
    if not weather_desc:
        weather_desc = 'pleasant weather natural lighting'
    spot_desc = SPOT_IMAGE_MAP.get(spot_name, f'{spot_name} scenic spot')
    prompt = (
        f'A stunning professional photograph of {spot_desc} in {city}, '
        f'the scene shows {weather_desc}, '
        f'the weather condition is clearly visible in the image, '
        f'professional travel photography, '
        f'high resolution 4K, cinematic composition, '
        f'natural colors, atmospheric lighting, '
        f'beautiful landscape photography, award winning photo'
    )
    return prompt


def generate_weather_image(city, weather_text, spots=None):
    try:
        spot_name = spots[0]['name'] if spots else None
        if not spot_name:
            return None
        
        cache_key = get_cache_key(city, weather_text, spot_name)
        cache = load_cache()
        
        if cache_key in cache:
            cached_data = cache[cache_key]
            logger.info(f"Cache hit for {city} - {spot_name} - {weather_text}")
            return cached_data.get('image_url')
        
        prompt = generate_weather_image_prompt(city, spot_name, weather_text)
        logger.info(f"Generating weather image for {city} - {spot_name} - {weather_text}")
        logger.info(f"Prompt: {prompt}")
        response = requests.post(
            AIGC_API_URL,
            headers={
                "Authorization": f"Bearer {AIGC_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": AIGC_MODEL,
                "prompt": prompt,
                "n": 1,
            },
            timeout=60,
        )
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response body: {response.text[:500]}")
        response.raise_for_status()
        result = response.json()
        logger.info(f"Image generation response: {result}")
        
        image_url = None
        if result.get("data"):
            image_url = result["data"][0].get("url")
            if image_url:
                cache[cache_key] = {
                    'city': city,
                    'weather': weather_text,
                    'spot': spot_name,
                    'image_url': image_url,
                    'created_at': time.time()
                }
                save_cache(cache)
                logger.info(f"Cache saved for {city} - {spot_name}")
                return image_url
            image_b64 = result["data"][0].get("b64_json")
            if image_b64:
                image_url = f"data:image/png;base64,{image_b64}"
                cache[cache_key] = {
                    'city': city,
                    'weather': weather_text,
                    'spot': spot_name,
                    'image_url': image_url,
                    'created_at': time.time()
                }
                save_cache(cache)
                logger.info(f"Cache saved for {city} - {spot_name}")
                return image_url
        return None
    except Exception as e:
        logger.error(f"Failed to generate weather image: {e}")
        return None
