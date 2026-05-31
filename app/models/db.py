# 数据库链接与建表
import json
import os
import sqlite3


def _project_root():
	return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))


# 获得数据文件的路径
DB_PATH = os.path.join(_project_root(), "database", "app.db")


def get_connection():
	os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn


def _get_table_columns(conn, table_name):
	rows = conn.execute(f"pragma table_info({table_name})").fetchall()
	return {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in rows}


def _ensure_column(conn, table_name, column_name, column_sql):
	columns = _get_table_columns(conn, table_name)
	if column_name not in columns:
		conn.execute(f"alter table {table_name} add column {column_sql}")


def _seed_functions(conn):
	default_functions = [
		{"parent_id": 0, "name": "系统管理", "code": "system", "icon": "layui-icon-set", "url": "", "type": 1, "sort": 1},
		{"parent_id": 0, "name": "模型引擎", "code": "model", "icon": "layui-icon-engine", "url": "", "type": 1, "sort": 2},
		{"parent_id": 0, "name": "瞭望管理", "code": "surveillance", "icon": "layui-icon-chart", "url": "", "type": 1, "sort": 3},
		{"parent_id": 0, "name": "数据仓库", "code": "data_warehouse", "icon": "layui-icon-table", "url": "", "type": 1, "sort": 4},
		{"parent_id": 0, "name": "数智大屏", "code": "data_screen", "icon": "layui-icon-chart-screen", "url": "", "type": 1, "sort": 5},
		{"parent_id": 0, "name": "智能舆情", "code": "smart_public_opinion", "icon": "layui-icon-notice", "url": "", "type": 1, "sort": 6},
		{"parent_id": 0, "name": "智能服务", "code": "smart_service", "icon": "layui-icon-dialogue", "url": "", "type": 1, "sort": 7},
		{"parent_id": 0, "name": "系统设置", "code": "system_setting", "icon": "layui-icon-set-fill", "url": "", "type": 1, "sort": 8},
	]

	for item in default_functions:
		row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
		if not row:
			conn.execute(
				"""
				insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
				values(?,?,?,?,?,?,?,1,datetime('now','localtime'),datetime('now','localtime'))
				""",
				(
					item["parent_id"],
					item["name"],
					item["code"],
					item["icon"],
					item["url"],
					item["type"],
					item["sort"],
				),
			)

	top_level_sort_map = {
		"system": 1,
		"model": 2,
		"surveillance": 3,
		"data_warehouse": 4,
		"data_screen": 5,
		"smart_public_opinion": 6,
		"smart_service": 7,
		"system_setting": 8,
	}
	for code, sort in top_level_sort_map.items():
		conn.execute(
			"""
			update functions
			set sort=?, update_at=datetime('now','localtime')
			where parent_id=0 and code=? and coalesce(sort, 0)<>?
			""",
			(sort, code, sort),
		)

	system_row = conn.execute("select id from functions where code='system'").fetchone()
	if not system_row:
		return

	system_id = system_row["id"]
	default_children = [
		{"name": "用户管理", "code": "system_user", "icon": "layui-icon-user", "url": "/admin/user/list", "sort": 1},
		{"name": "角色管理", "code": "system_role", "icon": "layui-icon-group", "url": "/admin/role/list", "sort": 2},
		{"name": "权限管理", "code": "system_permission", "icon": "layui-icon-auz", "url": "/admin/permission/list", "sort": 3},
		{"name": "功能管理", "code": "system_function", "icon": "layui-icon-component", "url": "/admin/function/list", "sort": 4},
	]

	for item in default_children:
		row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
		if not row:
			conn.execute(
				"""
				insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
				values(?,?,?,?,?,2,?,1,datetime('now','localtime'),datetime('now','localtime'))
				""",
				(
					system_id,
					item["name"],
					item["code"],
					item["icon"],
					item["url"],
					item["sort"],
				),
			)

	model_row = conn.execute("select id from functions where code='model'").fetchone()
	if model_row:
		model_id = model_row["id"]
		model_children = [
			{"name": "模型引擎", "code": "model_engine_list", "icon": "layui-icon-engine", "url": "/admin/model/list", "sort": 1},
		]
		for item in model_children:
			row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
			if not row:
				conn.execute(
					"""
					insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
					values(?,?,?,?,?,2,?,1,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(
						model_id,
						item["name"],
						item["code"],
						item["icon"],
						item["url"],
						item["sort"],
					),
				)

	surveillance_row = conn.execute("select id from functions where code='surveillance'").fetchone()
	if surveillance_row:
		surveillance_id = surveillance_row["id"]
		surveillance_children = [
			{"name": "采集源管理", "code": "surveillance_source_list", "icon": "layui-icon-template-1", "url": "/admin/surveillance/source/list", "sort": 1},
			{"name": "瞭望采集", "code": "surveillance_collect", "icon": "layui-icon-release", "url": "/admin/surveillance/collect", "sort": 2},
		]
		for item in surveillance_children:
			row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
			if not row:
				conn.execute(
					"""
					insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
					values(?,?,?,?,?,2,?,1,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(
						surveillance_id,
						item["name"],
						item["code"],
						item["icon"],
						item["url"],
						item["sort"],
					),
				)

	warehouse_row = conn.execute("select id from functions where code='data_warehouse'").fetchone()
	if warehouse_row:
		warehouse_id = warehouse_row["id"]
		warehouse_children = [
			{"name": "数据仓库", "code": "warehouse_surveillance_list", "icon": "layui-icon-table", "url": "/admin/warehouse/list", "sort": 1},
		]
		for item in warehouse_children:
			row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
			if not row:
				conn.execute(
					"""
					insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
					values(?,?,?,?,?,2,?,1,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(
						warehouse_id,
						item["name"],
						item["code"],
						item["icon"],
						item["url"],
						item["sort"],
					),
				)

	data_screen_row = conn.execute("select id from functions where code='data_screen'").fetchone()
	if data_screen_row:
		data_screen_id = data_screen_row["id"]
		data_screen_children = [
			{"name": "数智大屏", "code": "data_screen_dashboard", "icon": "layui-icon-chart-screen", "url": "/admin/data/screen", "sort": 1},
		]
		for item in data_screen_children:
			row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
			if not row:
				conn.execute(
					"""
					insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
					values(?,?,?,?,?,2,?,1,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(
						data_screen_id,
						item["name"],
						item["code"],
						item["icon"],
						item["url"],
						item["sort"],
					),
				)
			else:
				conn.execute(
					"""
					update functions
					set parent_id=?,name=?,icon=?,url=?,type=2,sort=?,update_at=datetime('now','localtime')
					where code=?
					""",
					(
						data_screen_id,
						item["name"],
						item["icon"],
						item["url"],
						item["sort"],
						item["code"],
					),
				)

	smart_public_opinion_row = conn.execute("select id from functions where code='smart_public_opinion'").fetchone()
	if smart_public_opinion_row:
		smart_public_opinion_id = smart_public_opinion_row["id"]
		smart_public_opinion_children = [
			{"name": "智能舆情", "code": "smart_public_opinion_list", "icon": "layui-icon-notice", "url": "/admin/opinion/list", "sort": 1},
		]
		for item in smart_public_opinion_children:
			row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
			if not row:
				conn.execute(
					"""
					insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
					values(?,?,?,?,?,2,?,1,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(
						smart_public_opinion_id,
						item["name"],
						item["code"],
						item["icon"],
						item["url"],
						item["sort"],
					),
				)
			else:
				conn.execute(
					"""
					update functions
					set parent_id=?,name=?,icon=?,url=?,type=2,sort=?,update_at=datetime('now','localtime')
					where code=?
					""",
					(
						smart_public_opinion_id,
						item["name"],
						item["icon"],
						item["url"],
						item["sort"],
						item["code"],
					),
				)

	system_setting_row = conn.execute("select id from functions where code='system_setting'").fetchone()
	if system_setting_row:
		system_setting_id = system_setting_row["id"]
		system_setting_children = [
			{"name": "接口管理", "code": "system_api_interface", "icon": "layui-icon-link", "url": "/admin/interface/list", "sort": 1},
		]
		for item in system_setting_children:
			row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
			if not row:
				conn.execute(
					"""
					insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
					values(?,?,?,?,?,2,?,1,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(
						system_setting_id,
						item["name"],
						item["code"],
						item["icon"],
						item["url"],
						item["sort"],
					),
				)

	smart_service_row = conn.execute("select id from functions where code='smart_service'").fetchone()
	if smart_service_row:
		smart_service_id = smart_service_row["id"]
		smart_service_children = [
			{"name": "数字员工", "code": "smart_digital_employee", "icon": "layui-icon-user", "url": "/admin/employee/list", "sort": 1},
			{"name": "智能聊天管理", "code": "smart_im_console", "icon": "layui-icon-chat", "url": "/admin/im/list", "sort": 2},
		]
		for item in smart_service_children:
			row = conn.execute("select id from functions where code=?", (item["code"],)).fetchone()
			if not row:
				conn.execute(
					"""
					insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
					values(?,?,?,?,?,2,?,1,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(
						smart_service_id,
						item["name"],
						item["code"],
						item["icon"],
						item["url"],
						item["sort"],
					),
				)


def _cleanup_legacy_functions(conn):
	legacy_smart_row = conn.execute("select id from functions where code='intelligent_service'").fetchone()
	new_smart_row = conn.execute("select id from functions where code='smart_service'").fetchone()
	if legacy_smart_row and new_smart_row:
		legacy_id = legacy_smart_row["id"]
		new_id = new_smart_row["id"]
		legacy_children = conn.execute(
			"select id,name,code,icon,url,sort,status from functions where parent_id=? order by sort asc,id asc",
			(legacy_id,),
		).fetchall()
		for child in legacy_children:
			exists = conn.execute("select id from functions where code=?", (child["code"],)).fetchone()
			if exists:
				conn.execute("delete from role_functions where function_id=?", (child["id"],))
				conn.execute("delete from functions where id=?", (child["id"],))
			else:
				conn.execute(
					"""
					update functions
					set parent_id=?, update_at=datetime('now','localtime')
					where id=?
					""",
					(new_id, child["id"]),
				)
		conn.execute("delete from role_functions where function_id=?", (legacy_id,))
		conn.execute("delete from functions where id=?", (legacy_id,))

	legacy_employee_row = conn.execute("select id from functions where code='digital_employee_list'").fetchone()
	new_employee_row = conn.execute("select id from functions where code='smart_digital_employee'").fetchone()
	if legacy_employee_row and new_employee_row:
		conn.execute("delete from role_functions where function_id=?", (legacy_employee_row["id"],))
		conn.execute("delete from functions where id=?", (legacy_employee_row["id"],))


def _seed_surveillance_sources(conn):
	default_headers = {
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
		"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.6",
		"Cache-Control": "no-cache",
		"Pragma": "no-cache",
		"Referer": "https://www.baidu.com/s?rtt=1&bsst=1&cl=2&tn=news&rsv_dl=ns_pc&word={keyword}",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
	}
	default_params = [
		{"name": "keyword", "label": "关键字", "required": 1, "default": "", "placeholder": "请输入瞭望关键字"},
		{"name": "pn", "label": "分页步进", "required": 0, "default": "0", "placeholder": "默认由系统自动计算"},
	]
	default_selectors = {
		"list_selector": "#content_left > div.result, #content_left > div.result-op, #content_left > div.c-container",
		"title_selector": "h3 a",
		"summary_selector": ".c-summary, .c-font-normal, .c-span-last, .content",
		"meta_selector": ".c-color-gray2, .c-color-gray, .c-title-author, .news-source",
	}

	source_row = conn.execute(
		"select id from surveillance_sources where code='baidu_news'",
	).fetchone()
	if not source_row:
		conn.execute(
			"""
			insert into surveillance_sources(
				name,code,description,entry_url_template,page_url_template,method,headers_json,params_json,
				selectors_json,page_step,default_page_count,default_limit,status,create_at,update_at
			) values(?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
			""",
			(
				"百度新闻采集源",
				"baidu_news",
				"百度新闻搜索结果采集源，支持关键字和分页步进动态采集。",
				"https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={keyword}",
				"https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={keyword}&pn={pn}",
				"GET",
				json.dumps(default_headers, ensure_ascii=False),
				json.dumps(default_params, ensure_ascii=False),
				json.dumps(default_selectors, ensure_ascii=False),
				10,
				2,
				20,
				1,
			),
		)


def _seed_api_endpoints(conn):
	default_items = [
		{
			"name": "网易云随机音乐",
			"code": "music_wy_rand",
			"url": "https://api.52vmy.cn/api/music/wy/rand",
			"method": "GET",
			"response_format": "JSON",
			"sample_url": "https://api.52vmy.cn/api/music/wy/rand",
			"default_qps": "每2秒最多4次，携带Token可无限制",
			"auth_note": "默认QPS：每2秒最多4次，携带Token可无限制",
			"remark": "随机返回网易云音乐数据。",
			"headers_json": "{}",
			"params_schema_json": "[]",
			"body_template": "",
			"timeout_seconds": 20,
			"status": 1,
		},
		{
			"name": "网易云排行榜",
			"code": "music_wy_top",
			"url": "https://api.52vmy.cn/api/music/wy/top",
			"method": "GET",
			"response_format": "JSON",
			"sample_url": "https://api.52vmy.cn/api/music/wy/top?t=1&n=20",
			"default_qps": "每2秒最多4次，携带Token可无限制",
			"auth_note": "默认QPS：每2秒最多4次，携带Token可无限制",
			"remark": "获取网易云音乐排行榜歌曲列表，支持原创榜/新歌榜/飙升榜/热歌榜，返回歌曲数组天然支持上下首切换。",
			"headers_json": "{}",
			"params_schema_json": json.dumps([
				{"name": "t", "label": "榜单", "required": 0, "default": "1", "placeholder": "1:原创榜/2:新歌榜/3:飙升榜/4:热歌榜"},
				{"name": "n", "label": "数量", "required": 0, "default": "20", "placeholder": "返回数量"}
			], ensure_ascii=False),
			"body_template": "",
			"timeout_seconds": 20,
			"status": 1,
		},
		{
			"name": "网易云音乐搜索",
			"code": "music_wy_search",
			"url": "https://apis.netstart.cn/music/search",
			"method": "GET",
			"response_format": "JSON",
			"sample_url": "https://apis.netstart.cn/music/search?keywords=周杰伦&limit=30",
			"default_qps": "注意频率控制",
			"auth_note": "基于NeteaseCloudMusicApi开源项目，无需认证。",
			"remark": "根据关键词搜索网易云音乐歌曲，支持歌手名、歌曲名、语种等搜索，返回免费可播放歌曲列表。",
			"headers_json": json.dumps({"Referer": "https://music.163.com/", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, ensure_ascii=False),
			"params_schema_json": json.dumps([
				{"name": "keywords", "label": "搜索关键词", "required": 1, "default": "", "placeholder": "歌手名、歌曲名或语种，如：日语歌、贾斯汀比伯、aespa"},
				{"name": "limit", "label": "返回数量", "required": 0, "default": "30", "placeholder": "最多返回歌曲数量"}
			], ensure_ascii=False),
			"body_template": "",
			"timeout_seconds": 30,
			"status": 1,
		},
		{
			"name": "三日天气查询",
			"code": "weather_tian",
			"url": "https://api.52vmy.cn/api/query/tian",
			"method": "GET",
			"response_format": "JSON",
			"sample_url": "https://api.52vmy.cn/api/query/tian?city=北京市",
			"default_qps": "每2秒最多4次，携带Token可无限制",
			"auth_note": "默认QPS：每2秒最多4次，携带Token可无限制",
			"remark": "点击前往三日天气API",
			"headers_json": "{}",
			"params_schema_json": json.dumps([
				{"name": "city", "label": "城市", "required": 1, "default": "北京市", "placeholder": "请输入城市名"}
			], ensure_ascii=False),
			"body_template": "",
			"timeout_seconds": 20,
			"status": 1,
		},
		{
			"name": "天气卡片背景图生成",
			"code": "weather_image_gen",
			"url": "https://aigc-api.aitoolcore.com/api/v1/images/generations",
			"method": "POST",
			"response_format": "JSON",
			"sample_url": "https://aigc-api.aitoolcore.com/api/v1/images/generations",
			"default_qps": "根据API限制",
			"auth_note": "需要Bearer Token认证",
			"remark": "AI图像生成API，用于生成天气卡片背景图，显示城市代表景点和当前天气联动效果，支持缓存避免重复生成",
			"headers_json": json.dumps({"Authorization": "Bearer sk-aigc-ff2029014b09dab5e86d1a22c5e1b81db6bb4e1f"}, ensure_ascii=False),
			"params_schema_json": json.dumps([
				{"name": "model", "label": "模型", "required": 1, "default": "qwen-image-plus", "placeholder": "模型名称"},
				{"name": "prompt", "label": "提示词", "required": 1, "default": "", "placeholder": "图像描述提示词"},
				{"name": "n", "label": "数量", "required": 1, "default": "1", "placeholder": "生成图片数量"}
			], ensure_ascii=False),
			"body_template": "",
			"timeout_seconds": 60,
			"status": 1,
		},
	]

	for item in default_items:
		row = conn.execute("select id from api_endpoints where code=?", (item["code"],)).fetchone()
		if not row:
			conn.execute(
				"""
				insert into api_endpoints(
					name,code,url,method,response_format,sample_url,default_qps,auth_note,remark,
					headers_json,params_schema_json,body_template,timeout_seconds,status,create_at,update_at
				) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
				""",
				(
					item["name"],
					item["code"],
					item["url"],
					item["method"],
					item["response_format"],
					item["sample_url"],
					item["default_qps"],
					item["auth_note"],
					item["remark"],
					item["headers_json"],
					item["params_schema_json"],
					item["body_template"],
					item["timeout_seconds"],
					item["status"],
				),
			)
		else:
			conn.execute(
				"""
				update api_endpoints
				set name=?,url=?,method=?,response_format=?,sample_url=?,default_qps=?,auth_note=?,remark=?,
				    headers_json=?,params_schema_json=?,body_template=?,timeout_seconds=?,status=?,update_at=datetime('now','localtime')
				where code=?
				""",
				(
					item["name"],
					item["url"],
					item["method"],
					item["response_format"],
					item["sample_url"],
					item["default_qps"],
					item["auth_note"],
					item["remark"],
					item["headers_json"],
					item["params_schema_json"],
					item["body_template"],
					item["timeout_seconds"],
					item["status"],
					item["code"],
				),
			)


def _seed_digital_employees(conn):
	weather_row = conn.execute("select id from api_endpoints where code='weather_tian'").fetchone()
	music_row = conn.execute("select id from api_endpoints where code='music_wy_rand'").fetchone()
	music_top_row = conn.execute("select id from api_endpoints where code='music_wy_top'").fetchone()
	music_search_row = conn.execute("select id from api_endpoints where code='music_wy_search'").fetchone()
	default_items = [
		{
			"name": "川小农",
			"alias": "川小农",
			"code": "employee_chuanxiaonong",
			"category": "AI",
			"model_id": None,
			"endpoint_id": None,
			"prompt": "你是数字员工“川小农”，擅长农业、校园、三农与政策相关问答。回答要专业、亲切、简洁，如果问题不明确，先主动澄清。",
			"api_param_name": "",
			"api_params_json": "{}",
			"response_template": "",
			"default_user_input": "请先做一个简短的自我介绍。",
			"description": "默认 AI 数字员工，使用系统默认模型和专属提示词提供智能对话服务。",
			"sort": 1,
			"status": 1,
		},
		{
			"name": "天气",
			"alias": "天气",
			"code": "employee_weather",
			"category": "普通",
			"model_id": None,
			"endpoint_id": weather_row["id"] if weather_row else None,
			"prompt": "",
			"api_param_name": "city",
			"api_params_json": "{}",
			"response_template": "【{data.city}】天气：{data.weather}，温度 {data.tempn}~{data.temp}，风向 {data.wind}，风速 {data.windSpeed}，空气质量 {data.current.air}。",
			"default_user_input": "",
			"description": "通过天气查询接口提供城市天气响应，用户使用 @天气城市名 进行调用。",
			"sort": 2,
			"status": 1,
		},
		{
			"name": "音乐",
			"alias": "音乐",
			"code": "employee_music",
			"category": "普通",
			"model_id": None,
			"endpoint_id": music_search_row["id"] if music_search_row else (music_top_row["id"] if music_top_row else (music_row["id"] if music_row else None)),
			"prompt": "你是音乐助手。根据用户的输入提取搜索关键词：\n- 如果用户说来首日语歌、日语音乐等，关键词为日语\n- 如果用户提到歌手名如贾斯汀比伯、aespa、周杰伦等，关键词为该歌手名\n- 如果用户提到语种如韩语歌、英文歌、日文歌等，关键词为该语种\n- 如果用户没有特定要求，关键词为热歌\n只返回关键词，不要其他内容。",
			"api_param_name": "keywords",
			"api_params_json": "{}",
			"response_template": "",
			"default_user_input": "热歌",
			"description": "智能音乐助手，支持根据用户输入搜索特定语种、歌手的歌曲。用户使用 @音乐 来首日语歌 或 @音乐 贾斯汀比伯 即可调用。返回音乐卡片格式数据。",
			"sort": 3,
			"status": 1,
		},
		{
			"name": "川农小助手",
			"alias": "川农小助手",
			"code": "employee_scau_assistant",
			"category": "AI",
			"model_id": None,
			"endpoint_id": None,
			"prompt": "你是数字员工“川农小助手”，仅围绕四川农业大学、校园学习、农业科研、三农政策与校园服务问题提供专业回答。若问题明显超出范围，要礼貌说明范围限制，并引导用户聚焦到四川农业大学相关主题。回答要准确、自然、支持多轮对话。",
			"api_param_name": "",
			"api_params_json": "{}",
			"response_template": "",
			"default_user_input": "请做一个面向四川农业大学同学的简短自我介绍。",
			"description": "限定四川农业大学范围的 AI 数字员工，用于校园与三农相关咨询。",
			"sort": 4,
			"status": 1,
		},
		{
			"name": "毒鸡汤小助手",
			"alias": "毒鸡汤",
			"code": "employee_toxic_soup",
			"category": "AI",
			"model_id": None,
			"endpoint_id": None,
			"prompt": "你是数字员工“毒鸡汤小助手”。你的任务是每次输出 1 到 3 句简短、有反差感、偏调侃风格的毒鸡汤文案，语言要俏皮，不要低俗、攻击、歧视或违法内容。如果用户有主题要求，就围绕主题生成。",
			"api_param_name": "",
			"api_params_json": "{}",
			"response_template": "",
			"default_user_input": "来一句毒鸡汤。",
			"description": "用于随机生成简短毒鸡汤内容的 AI 员工。",
			"sort": 5,
			"status": 1,
		},
	]

	for item in default_items:
		row = conn.execute("select id from digital_employees where code=?", (item["code"],)).fetchone()
		if not row:
			conn.execute(
				"""
				insert into digital_employees(
					name,alias,code,category,model_id,endpoint_id,prompt,api_param_name,api_params_json,
					response_template,default_user_input,description,sort,status,create_at,update_at
				) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
				""",
				(
					item["name"],
					item["alias"],
					item["code"],
					item["category"],
					item["model_id"],
					item["endpoint_id"],
					item["prompt"],
					item["api_param_name"],
					item["api_params_json"],
					item["response_template"],
					item["default_user_input"],
					item["description"],
					item["sort"],
					item["status"],
				),
			)
		else:
			conn.execute(
				"""
				update digital_employees
				set
					category=case when coalesce(category,'')='' then ? else category end,
					model_id=case when model_id is null and ? is not null then ? else model_id end,
					endpoint_id=case when endpoint_id is null and ? is not null then ? else endpoint_id end,
					prompt=case when coalesce(prompt,'')='' then ? else prompt end,
					api_param_name=case when coalesce(api_param_name,'')='' then ? else api_param_name end,
					api_params_json=case when coalesce(api_params_json,'') in ('', '{}') then ? else api_params_json end,
					response_template=case when coalesce(response_template,'')='' then ? else response_template end,
					default_user_input=case when coalesce(default_user_input,'')='' then ? else default_user_input end,
					description=case when coalesce(description,'')='' then ? else description end,
					sort=case when coalesce(sort,0)=0 then ? else sort end,
					update_at=datetime('now','localtime')
				where id=?
				""",
				(
					item["category"],
					item["model_id"],
					item["model_id"],
					item["endpoint_id"],
					item["endpoint_id"],
					item["prompt"],
					item["api_param_name"],
					item["api_params_json"],
					item["response_template"],
					item["default_user_input"],
					item["description"],
					item["sort"],
					row["id"],
				),
			)


def _seed_im_defaults(conn):
	server_items = [
		{
			"name": "本地轮询聊天服务",
			"code": "local_im_polling",
			"protocol": "polling",
			"base_url": "http://localhost:10086",
			"health_url": "/admin/welcome",
			"weight": 100,
			"priority": 1,
			"status": 1,
			"remark": "默认本地聊天服务配置，预留未来多服务切换与健康检查能力。",
		}
	]
	for item in server_items:
		row = conn.execute("select id from im_chat_servers where code=?", (item["code"],)).fetchone()
		if not row:
			conn.execute(
				"""
				insert into im_chat_servers(
					name,code,protocol,base_url,health_url,weight,priority,status,last_health_status,last_error,remark,create_at,update_at
				) values(?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
				""",
				(
					item["name"],
					item["code"],
					item["protocol"],
					item["base_url"],
					item["health_url"],
					item["weight"],
					item["priority"],
					item["status"],
					"healthy",
					"",
					item["remark"],
				),
			)

	tool_items = [
		{
			"name": "天气接口工具",
			"code": "tool_weather_endpoint",
			"tool_type": "endpoint",
			"endpoint_code": "weather_tian",
			"description": "为数字员工提供天气查询能力。",
		},
		{
			"name": "音乐接口工具",
			"code": "tool_music_endpoint",
			"tool_type": "endpoint",
			"endpoint_code": "music_wy_search",
			"description": "为数字员工提供网易云音乐搜索能力，支持关键词搜索歌曲。",
		},
		{
			"name": "校园知识顾问工具",
			"code": "tool_scau_prompt",
			"tool_type": "prompt",
			"endpoint_code": "",
			"description": "为四川农业大学相关数字员工预留工具配置。",
		},
	]
	for item in tool_items:
		endpoint_id = None
		if item["endpoint_code"]:
			endpoint_row = conn.execute("select id from api_endpoints where code=?", (item["endpoint_code"],)).fetchone()
			endpoint_id = endpoint_row["id"] if endpoint_row else None
		row = conn.execute("select id from im_ai_tools where code=?", (item["code"],)).fetchone()
		if not row:
			conn.execute(
				"""
				insert into im_ai_tools(name,code,tool_type,endpoint_id,description,config_json,status,create_at,update_at)
				values(?,?,?,?,?,'{}',1,datetime('now','localtime'),datetime('now','localtime'))
				""",
				(item["name"], item["code"], item["tool_type"], endpoint_id, item["description"]),
			)

	binding_items = [
		("employee_weather", "tool_weather_endpoint", "all"),
		("employee_music", "tool_music_endpoint", "all"),
		("employee_scau_assistant", "tool_scau_prompt", "all"),
	]
	for employee_code, tool_code, role_scope in binding_items:
		employee_row = conn.execute("select id from digital_employees where code=?", (employee_code,)).fetchone()
		tool_row = conn.execute("select id from im_ai_tools where code=?", (tool_code,)).fetchone()
		if not employee_row or not tool_row:
			continue
		exists = conn.execute(
			"select 1 from im_employee_tools where employee_id=? and tool_id=?",
			(employee_row["id"], tool_row["id"]),
		).fetchone()
		if not exists:
			conn.execute(
				"insert into im_employee_tools(employee_id,tool_id,role_scope,create_at) values(?,?,?,datetime('now','localtime'))",
				(employee_row["id"], tool_row["id"], role_scope),
			)


def _seed_roles(conn):
	role_row = conn.execute("select id from roles where code='super_admin'").fetchone()
	if role_row:
		role_id = role_row["id"]
	else:
		cursor = conn.execute(
			"""
			insert into roles(name,code,description,sort,status,is_system,create_at,update_at)
			values(?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
			""",
			("超级管理员", "super_admin", "系统最高权限角色，拥有所有功能权限", 1, 1, 1),
		)
		role_id = cursor.lastrowid

	function_rows = conn.execute("select id from functions where status=1").fetchall()
	for row in function_rows:
		exists = conn.execute(
			"select 1 from role_functions where role_id=? and function_id=?",
			(role_id, row["id"]),
		).fetchone()
		if not exists:
			conn.execute(
				"insert into role_functions(role_id,function_id) values(?,?)",
				(role_id, row["id"]),
			)

	admin_user_row = conn.execute(
		"select id from users where username='admin'"
	).fetchone()
	if admin_user_row:
		conn.execute(
			"update users set role=?, status=1, update_at=datetime('now','localtime') where username='admin'",
			("超级管理员",),
		)

	default_roles = [
		("普通用户", "normal_user", "前端用户默认角色，可使用智能问数、数字员工与历史会话能力", 20, 0),
		("会员用户", "member_user", "预留会员订阅角色，当前版本仅做角色预置，不开放专属功能", 21, 0),
	]
	for name, code, description, sort, is_system in default_roles:
		exists = conn.execute("select id from roles where code=?", (code,)).fetchone()
		if exists:
			conn.execute(
				"""
				update roles
				set name=?,description=?,sort=?,status=1,update_at=datetime('now','localtime')
				where id=?
				""",
				(name, description, sort, exists["id"]),
			)
		else:
			conn.execute(
				"""
				insert into roles(name,code,description,sort,status,is_system,create_at,update_at)
				values(?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
				""",
				(name, code, description, sort, 1, is_system),
			)


def init_db():
	from app.models.scheduler import ScheduledTask, TaskLog
	from app.models.workflow import Workflow, WorkflowLog, GestureRecord
	
	with get_connection() as conn:
		# 初始化定时任务表
		ScheduledTask.init_table()
		TaskLog.init_table()
		
		# 初始化工作流表
		Workflow.init_table()
		WorkflowLog.init_table()
		
		# 初始化手势记录表
		GestureRecord.init_table()
		
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS users(
				id integer PRIMARY KEY AUTOINCREMENT,
				username TEXT NOT NULL UNIQUE,
				password_hash TEXT NOT NULL,
				salt TEXT NOT NULL,
				email TEXT DEFAULT '',
				phone TEXT DEFAULT '',
				role TEXT DEFAULT 'user',
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS functions(
				id integer PRIMARY KEY AUTOINCREMENT,
				parent_id INTEGER DEFAULT 0,
				name TEXT NOT NULL,
				code TEXT NOT NULL UNIQUE,
				icon TEXT DEFAULT '',
				url TEXT DEFAULT '',
				type INTEGER DEFAULT 1,
				sort INTEGER DEFAULT 0,
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS roles(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				code TEXT NOT NULL UNIQUE,
				description TEXT DEFAULT '',
				sort INTEGER DEFAULT 0,
				status INTEGER DEFAULT 1,
				is_system INTEGER DEFAULT 0,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS role_functions(
				role_id INTEGER NOT NULL,
				function_id INTEGER NOT NULL,
				PRIMARY KEY(role_id, function_id)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS model_services(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				provider TEXT DEFAULT 'openai-compatible',
				base_url TEXT NOT NULL,
				api_path TEXT DEFAULT '/chat/completions',
				api_key TEXT NOT NULL,
				model_name TEXT NOT NULL,
				system_prompt TEXT DEFAULT '',
				temperature REAL DEFAULT 0.7,
				max_tokens INTEGER DEFAULT 2048,
				timeout_seconds INTEGER DEFAULT 60,
				enable_sse INTEGER DEFAULT 1,
				is_default INTEGER DEFAULT 0,
				status INTEGER DEFAULT 1,
				description TEXT DEFAULT '',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS model_usage_logs(
				id integer PRIMARY KEY AUTOINCREMENT,
				model_id INTEGER NOT NULL,
				model_name TEXT NOT NULL,
				request_preview TEXT DEFAULT '',
				response_preview TEXT DEFAULT '',
				prompt_tokens INTEGER DEFAULT 0,
				completion_tokens INTEGER DEFAULT 0,
				total_tokens INTEGER DEFAULT 0,
				response_ms INTEGER DEFAULT 0,
				success INTEGER DEFAULT 1,
				error_message TEXT DEFAULT '',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS surveillance_sources(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				code TEXT NOT NULL UNIQUE,
				description TEXT DEFAULT '',
				entry_url_template TEXT NOT NULL,
				page_url_template TEXT NOT NULL,
				method TEXT DEFAULT 'GET',
				headers_json TEXT DEFAULT '{}',
				params_json TEXT DEFAULT '[]',
				selectors_json TEXT DEFAULT '{}',
				page_step INTEGER DEFAULT 10,
				default_page_count INTEGER DEFAULT 1,
				default_limit INTEGER DEFAULT 20,
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS surveillance_records(
				id integer PRIMARY KEY AUTOINCREMENT,
				source_id INTEGER NOT NULL,
				source_name TEXT NOT NULL,
				keyword TEXT NOT NULL,
				page_no INTEGER DEFAULT 1,
				title TEXT NOT NULL,
				url TEXT NOT NULL,
				summary TEXT DEFAULT '',
				origin_site TEXT DEFAULT '',
				publish_time TEXT DEFAULT '',
				raw_json TEXT DEFAULT '{}',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				UNIQUE(source_id, keyword, url)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS surveillance_record_details(
				id integer PRIMARY KEY AUTOINCREMENT,
				record_id INTEGER NOT NULL,
				task_id INTEGER,
				source_id INTEGER,
				source_name TEXT DEFAULT '',
				keyword TEXT DEFAULT '',
				title TEXT DEFAULT '',
				url TEXT DEFAULT '',
				page_title TEXT DEFAULT '',
				content_markdown TEXT DEFAULT '',
				content_text TEXT DEFAULT '',
				content_html TEXT DEFAULT '',
				extract_engine TEXT DEFAULT 'raw4ai-fallback',
				extract_status INTEGER DEFAULT 1,
				ai_summary TEXT DEFAULT '',
				ai_keywords_json TEXT DEFAULT '[]',
				ai_key_points_json TEXT DEFAULT '[]',
				ai_entities_json TEXT DEFAULT '[]',
				ai_sentiment TEXT DEFAULT '',
				ai_score INTEGER DEFAULT 0,
				model_id INTEGER,
				model_name TEXT DEFAULT '',
				prompt_tokens INTEGER DEFAULT 0,
				completion_tokens INTEGER DEFAULT 0,
				total_tokens INTEGER DEFAULT 0,
				response_ms INTEGER DEFAULT 0,
				error_message TEXT DEFAULT '',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS surveillance_deep_tasks(
				id integer PRIMARY KEY AUTOINCREMENT,
				batch_no TEXT NOT NULL UNIQUE,
				record_ids_json TEXT DEFAULT '[]',
				total_count INTEGER DEFAULT 0,
				success_count INTEGER DEFAULT 0,
				failed_count INTEGER DEFAULT 0,
				total_tokens INTEGER DEFAULT 0,
				avg_score REAL DEFAULT 0,
				status TEXT DEFAULT 'pending',
				error_message TEXT DEFAULT '',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS surveillance_deep_logs(
				id integer PRIMARY KEY AUTOINCREMENT,
				task_id INTEGER NOT NULL,
				record_id INTEGER,
				level TEXT DEFAULT 'info',
				message TEXT NOT NULL,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS api_endpoints(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				code TEXT NOT NULL UNIQUE,
				url TEXT NOT NULL,
				method TEXT NOT NULL DEFAULT 'GET',
				response_format TEXT DEFAULT 'JSON',
				sample_url TEXT DEFAULT '',
				default_qps TEXT DEFAULT '',
				auth_note TEXT DEFAULT '',
				remark TEXT DEFAULT '',
				headers_json TEXT DEFAULT '{}',
				params_schema_json TEXT DEFAULT '[]',
				body_template TEXT DEFAULT '',
				timeout_seconds INTEGER DEFAULT 20,
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS digital_employees(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				alias TEXT NOT NULL UNIQUE,
				code TEXT NOT NULL UNIQUE,
				category TEXT NOT NULL DEFAULT 'AI',
				model_id INTEGER,
				endpoint_id INTEGER,
				prompt TEXT DEFAULT '',
				api_param_name TEXT DEFAULT '',
				api_params_json TEXT DEFAULT '{}',
				response_template TEXT DEFAULT '',
				default_user_input TEXT DEFAULT '',
				description TEXT DEFAULT '',
				sort INTEGER DEFAULT 0,
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS data_screen_nodes(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				code TEXT NOT NULL UNIQUE,
				lat REAL DEFAULT 0,
				lng REAL DEFAULT 0,
				category TEXT DEFAULT 'default',
				value REAL DEFAULT 0,
				extra_json TEXT DEFAULT '{}',
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS data_screen_wordcloud(
				id integer PRIMARY KEY AUTOINCREMENT,
				word TEXT NOT NULL,
				frequency INTEGER DEFAULT 1,
				source_type TEXT DEFAULT 'chat',
				source_id INTEGER,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS public_opinion_analysis(
				id integer PRIMARY KEY AUTOINCREMENT,
				title TEXT NOT NULL,
				content TEXT DEFAULT '',
				sentiment TEXT DEFAULT '中性',
				score INTEGER DEFAULT 0,
				keywords_json TEXT DEFAULT '[]',
				source_type TEXT DEFAULT 'auto',
				source_ids_json TEXT DEFAULT '[]',
				model_name TEXT DEFAULT '',
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS user_chat_sessions(
				id integer PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER NOT NULL,
				username TEXT NOT NULL,
				title TEXT NOT NULL,
				model_id INTEGER,
				model_name TEXT DEFAULT '',
				last_message_preview TEXT DEFAULT '',
				last_intent TEXT DEFAULT '',
				message_count INTEGER DEFAULT 0,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS user_chat_messages(
				id integer PRIMARY KEY AUTOINCREMENT,
				session_id INTEGER NOT NULL,
				user_id INTEGER NOT NULL,
				role TEXT NOT NULL,
				message_type TEXT DEFAULT 'chat',
				intent TEXT DEFAULT '',
				model_id INTEGER,
				model_name TEXT DEFAULT '',
				content_text TEXT DEFAULT '',
				content_markdown TEXT DEFAULT '',
				extra_json TEXT DEFAULT '{}',
				prompt_tokens INTEGER DEFAULT 0,
				completion_tokens INTEGER DEFAULT 0,
				total_tokens INTEGER DEFAULT 0,
				response_ms INTEGER DEFAULT 0,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_friendships(
				id integer PRIMARY KEY AUTOINCREMENT,
				user_low_id INTEGER NOT NULL,
				user_high_id INTEGER NOT NULL,
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				UNIQUE(user_low_id, user_high_id)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_conversations(
				id integer PRIMARY KEY AUTOINCREMENT,
				chat_type TEXT NOT NULL DEFAULT 'private',
				name TEXT DEFAULT '',
				owner_user_id INTEGER DEFAULT 0,
				group_id INTEGER,
				employee_id INTEGER,
				private_key TEXT DEFAULT '',
				last_message_preview TEXT DEFAULT '',
				last_sender_name TEXT DEFAULT '',
				last_message_type TEXT DEFAULT 'text',
				last_message_at TEXT DEFAULT '',
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_conversation_members(
				id integer PRIMARY KEY AUTOINCREMENT,
				conversation_id INTEGER NOT NULL,
				member_type TEXT NOT NULL DEFAULT 'user',
				user_id INTEGER,
				employee_id INTEGER,
				role TEXT DEFAULT 'member',
				status INTEGER DEFAULT 1,
				joined_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_groups(
				id integer PRIMARY KEY AUTOINCREMENT,
				conversation_id INTEGER NOT NULL UNIQUE,
				name TEXT NOT NULL,
				owner_user_id INTEGER NOT NULL,
				notice TEXT DEFAULT '',
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_private_messages(
				id integer PRIMARY KEY AUTOINCREMENT,
				conversation_id INTEGER NOT NULL,
				sender_type TEXT NOT NULL DEFAULT 'user',
				sender_user_id INTEGER,
				sender_employee_id INTEGER,
				receiver_user_id INTEGER,
				receiver_employee_id INTEGER,
				content_type TEXT DEFAULT 'text',
				content_text TEXT DEFAULT '',
				file_id INTEGER,
				extra_json TEXT DEFAULT '{}',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_group_messages(
				id integer PRIMARY KEY AUTOINCREMENT,
				conversation_id INTEGER NOT NULL,
				group_id INTEGER NOT NULL,
				sender_type TEXT NOT NULL DEFAULT 'user',
				sender_user_id INTEGER,
				sender_employee_id INTEGER,
				content_type TEXT DEFAULT 'text',
				content_text TEXT DEFAULT '',
				file_id INTEGER,
				extra_json TEXT DEFAULT '{}',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_files(
				id integer PRIMARY KEY AUTOINCREMENT,
				file_hash TEXT NOT NULL UNIQUE,
				original_name TEXT NOT NULL,
				storage_name TEXT NOT NULL,
				file_ext TEXT DEFAULT '',
				mime_type TEXT DEFAULT '',
				size_bytes INTEGER DEFAULT 0,
				relative_path TEXT NOT NULL,
				upload_user_id INTEGER NOT NULL,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_chat_servers(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				code TEXT NOT NULL UNIQUE,
				protocol TEXT DEFAULT 'polling',
				base_url TEXT DEFAULT '',
				health_url TEXT DEFAULT '',
				weight INTEGER DEFAULT 100,
				priority INTEGER DEFAULT 1,
				status INTEGER DEFAULT 1,
				last_health_status TEXT DEFAULT 'unknown',
				last_error TEXT DEFAULT '',
				remark TEXT DEFAULT '',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_announcements(
				id integer PRIMARY KEY AUTOINCREMENT,
				group_id INTEGER NOT NULL,
				title TEXT NOT NULL,
				content TEXT NOT NULL,
				status INTEGER DEFAULT 1,
				published_by INTEGER NOT NULL,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_ai_tools(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				code TEXT NOT NULL UNIQUE,
				tool_type TEXT NOT NULL DEFAULT 'endpoint',
				endpoint_id INTEGER,
				description TEXT DEFAULT '',
				config_json TEXT DEFAULT '{}',
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				update_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS im_employee_tools(
				id integer PRIMARY KEY AUTOINCREMENT,
				employee_id INTEGER NOT NULL,
				tool_id INTEGER NOT NULL,
				role_scope TEXT DEFAULT 'all',
				create_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				UNIQUE(employee_id, tool_id)
			)
			"""
		)
		_ensure_column(conn, "digital_employees", "code", "code TEXT DEFAULT ''")
		_ensure_column(conn, "digital_employees", "endpoint_id", "endpoint_id INTEGER")
		_ensure_column(conn, "digital_employees", "prompt", "prompt TEXT DEFAULT ''")
		_ensure_column(conn, "digital_employees", "api_param_name", "api_param_name TEXT DEFAULT ''")
		_ensure_column(conn, "digital_employees", "api_params_json", "api_params_json TEXT DEFAULT '{}'")
		_ensure_column(conn, "digital_employees", "response_template", "response_template TEXT DEFAULT ''")
		_ensure_column(conn, "digital_employees", "default_user_input", "default_user_input TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_records", "deep_status", "deep_status INTEGER DEFAULT 0")
		_ensure_column(conn, "surveillance_records", "deep_collect_at", "deep_collect_at TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_records", "deep_detail_id", "deep_detail_id INTEGER")
		_ensure_column(conn, "surveillance_records", "deep_task_id", "deep_task_id INTEGER")
		_ensure_column(conn, "surveillance_records", "deep_error_message", "deep_error_message TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "task_id", "task_id INTEGER")
		_ensure_column(conn, "surveillance_record_details", "source_id", "source_id INTEGER")
		_ensure_column(conn, "surveillance_record_details", "source_name", "source_name TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "keyword", "keyword TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "title", "title TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "url", "url TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "page_title", "page_title TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "content_markdown", "content_markdown TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "content_text", "content_text TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "content_html", "content_html TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "ai_summary", "ai_summary TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "ai_keywords_json", "ai_keywords_json TEXT DEFAULT '[]'")
		_ensure_column(conn, "surveillance_record_details", "ai_key_points_json", "ai_key_points_json TEXT DEFAULT '[]'")
		_ensure_column(conn, "surveillance_record_details", "ai_entities_json", "ai_entities_json TEXT DEFAULT '[]'")
		_ensure_column(conn, "surveillance_record_details", "ai_sentiment", "ai_sentiment TEXT DEFAULT ''")
		_ensure_column(conn, "surveillance_record_details", "ai_score", "ai_score INTEGER DEFAULT 0")
		_ensure_column(conn, "surveillance_record_details", "prompt_tokens", "prompt_tokens INTEGER DEFAULT 0")
		_ensure_column(conn, "surveillance_record_details", "completion_tokens", "completion_tokens INTEGER DEFAULT 0")
		_ensure_column(conn, "surveillance_record_details", "total_tokens", "total_tokens INTEGER DEFAULT 0")
		_ensure_column(conn, "surveillance_record_details", "response_ms", "response_ms INTEGER DEFAULT 0")
		_ensure_column(conn, "surveillance_record_details", "error_message", "error_message TEXT DEFAULT ''")
		_ensure_column(conn, "user_chat_sessions", "last_intent", "last_intent TEXT DEFAULT ''")
		_ensure_column(conn, "user_chat_sessions", "message_count", "message_count INTEGER DEFAULT 0")
		_ensure_column(conn, "user_chat_messages", "message_type", "message_type TEXT DEFAULT 'chat'")
		_ensure_column(conn, "user_chat_messages", "intent", "intent TEXT DEFAULT ''")
		_ensure_column(conn, "user_chat_messages", "model_id", "model_id INTEGER")
		_ensure_column(conn, "user_chat_messages", "model_name", "model_name TEXT DEFAULT ''")
		_ensure_column(conn, "user_chat_messages", "content_markdown", "content_markdown TEXT DEFAULT ''")
		_ensure_column(conn, "user_chat_messages", "extra_json", "extra_json TEXT DEFAULT '{}'")
		_ensure_column(conn, "user_chat_messages", "prompt_tokens", "prompt_tokens INTEGER DEFAULT 0")
		_ensure_column(conn, "user_chat_messages", "completion_tokens", "completion_tokens INTEGER DEFAULT 0")
		_ensure_column(conn, "user_chat_messages", "total_tokens", "total_tokens INTEGER DEFAULT 0")
		_ensure_column(conn, "user_chat_messages", "response_ms", "response_ms INTEGER DEFAULT 0")
		_ensure_column(conn, "users", "avatar_path", "avatar_path TEXT DEFAULT ''")
		_ensure_column(conn, "im_conversation_members", "last_read_at", "last_read_at TEXT DEFAULT ''")
		_ensure_column(conn, "im_friendships", "requester_user_id", "requester_user_id INTEGER DEFAULT 0")
		_ensure_column(conn, "im_friendships", "target_user_id", "target_user_id INTEGER DEFAULT 0")
		_ensure_column(conn, "im_friendships", "action_user_id", "action_user_id INTEGER DEFAULT 0")
		_ensure_column(conn, "im_friendships", "action_at", "action_at TEXT DEFAULT ''")
		conn.execute(
			"""
			update im_conversation_members
			set last_read_at=coalesce(nullif(last_read_at, ''), joined_at)
			where coalesce(last_read_at, '')=''
			"""
		)
		conn.execute(
			"""
			update im_friendships
			set requester_user_id=coalesce(nullif(requester_user_id, 0), user_low_id),
			    target_user_id=coalesce(nullif(target_user_id, 0), user_high_id)
			where coalesce(requester_user_id, 0)=0 or coalesce(target_user_id, 0)=0
			"""
		)
		conn.execute(
			"""
			update im_friendships
			set action_user_id=coalesce(nullif(action_user_id, 0), target_user_id),
			    action_at=coalesce(nullif(action_at, ''), update_at)
			where status=1 and (coalesce(action_user_id, 0)=0 or coalesce(action_at, '')='')
			"""
		)

		employee_columns = _get_table_columns(conn, "digital_employees")
		detail_columns = _get_table_columns(conn, "surveillance_record_details")
		if "param_name" in employee_columns:
			conn.execute(
				"""
				update digital_employees
				set api_param_name=coalesce(nullif(api_param_name,''), param_name)
				where coalesce(api_param_name,'')=''
				"""
			)
		if "fixed_params_json" in employee_columns:
			conn.execute(
				"""
				update digital_employees
				set api_params_json=coalesce(nullif(api_params_json,''), fixed_params_json)
				where coalesce(api_params_json,'') in ('', '{}')
				"""
			)
		if "system_prompt" in employee_columns:
			conn.execute(
				"""
				update digital_employees
				set prompt=coalesce(nullif(prompt,''), system_prompt)
				where coalesce(prompt,'')=''
				"""
			)
		if "welcome_text" in employee_columns:
			conn.execute(
				"""
				update digital_employees
				set default_user_input=coalesce(nullif(default_user_input,''), welcome_text)
				where coalesce(default_user_input,'')=''
				"""
			)
		conn.execute(
			"""
			update digital_employees
			set response_template=replace(response_template, '{data.air}', '{data.current.air}')
			where alias='天气' and response_template like '%{data.air}%'
			"""
		)
		conn.execute("update digital_employees set code='employee_chuanxiaonong' where alias='川小农' and coalesce(code,'')=''")
		conn.execute("update digital_employees set code='employee_weather' where alias='天气' and coalesce(code,'')=''")
		conn.execute("update digital_employees set code='employee_music' where alias='音乐' and coalesce(code,'')=''")
		conn.execute("update digital_employees set code='employee_' || id where coalesce(code,'')=''")
		if "record_title" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set title=coalesce(nullif(title,''), record_title)
				where coalesce(title,'')=''
				"""
			)
		if "record_url" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set url=coalesce(nullif(url,''), record_url)
				where coalesce(url,'')=''
				"""
			)
		if "extracted_title" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set page_title=coalesce(nullif(page_title,''), extracted_title)
				where coalesce(page_title,'')=''
				"""
			)
		if "extracted_markdown" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set content_markdown=coalesce(nullif(content_markdown,''), extracted_markdown)
				where coalesce(content_markdown,'')=''
				"""
			)
		if "extracted_text" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set content_text=coalesce(nullif(content_text,''), extracted_text)
				where coalesce(content_text,'')=''
				"""
			)
		if "extracted_html" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set content_html=coalesce(nullif(content_html,''), extracted_html)
				where coalesce(content_html,'')=''
				"""
			)
		if "summary" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set ai_summary=coalesce(nullif(ai_summary,''), summary)
				where coalesce(ai_summary,'')=''
				"""
			)
		if "stats_json" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set total_tokens=coalesce(total_tokens, 0)
				where total_tokens is null
				"""
			)
		if "analysis_json" in detail_columns:
			conn.execute(
				"""
				update surveillance_record_details
				set ai_keywords_json=coalesce(nullif(ai_keywords_json,''), '[]')
				where coalesce(ai_keywords_json,'')=''
				"""
			)

		_seed_functions(conn)
		_cleanup_legacy_functions(conn)
		_seed_roles(conn)
		_seed_surveillance_sources(conn)
		_seed_api_endpoints(conn)
		_seed_digital_employees(conn)
		_seed_im_defaults(conn)
		if "endpoint_code" in employee_columns:
			conn.execute(
				"""
				update digital_employees
				set endpoint_id=(
					select id from api_endpoints where code=digital_employees.endpoint_code limit 1
				)
				where endpoint_id is null and coalesce(endpoint_code,'')<>''
				"""
			)


class MySQLConnectionWrapper:
	def __init__(self, connection):
		self._conn = connection
		self._cursor = None

	def execute(self, sql, params=None):
		if self._cursor is None:
			self._cursor = self._conn.cursor()
		converted_sql = self._adapt_sql(sql)
		try:
			if params:
				return self._cursor.execute(converted_sql, params)
			else:
				return self._cursor.execute(converted_sql)
		except Exception as e:
			raise RuntimeError(f"MySQL执行错误: {e}\nSQL: {converted_sql}")

	def executemany(self, sql, params_list):
		if self._cursor is None:
			self._cursor = self._conn.cursor()
		converted_sql = self._adapt_sql(sql)
		try:
			return self._cursor.executemany(converted_sql, params_list)
		except Exception as e:
			raise RuntimeError(f"MySQL批量执行错误: {e}\nSQL: {converted_sql}")

	def fetchall(self):
		if self._cursor:
			return self._cursor.fetchall()
		return []

	def fetchone(self):
		if self._cursor:
			return self._cursor.fetchone()
		return None

	def lastrowid(self):
		if self._cursor:
			return self._cursor.lastrowid
		return None

	def rowcount(self):
		if self._cursor:
			return self._cursor.rowcount
		return 0

	def close(self):
		if self._cursor:
			self._cursor.close()
			self._cursor = None

	def _adapt_sql(self, sql):
		import re
		sql = re.sub(r'\bAUTOINCREMENT\b', 'AUTO_INCREMENT', sql, flags=re.IGNORECASE)
		sql = re.sub(r"datetime\('now','localtime'\)", 'NOW()', sql, flags=re.IGNORECASE)
		sql = re.sub(r"datetime\('now'\)", 'NOW()', sql, flags=re.IGNORECASE)
		sql = re.sub(r'\bTEXT\b(?=.*DEFAULT\s)', 'VARCHAR(255)', sql, flags=re.IGNORECASE | re.DOTALL)
		sql = re.sub(r'pragma table_info\((\w+)\)', r'SHOW COLUMNS FROM \1', sql, flags=re.IGNORECASE)
		return sql


class DatabaseAdapter:
	def __init__(self, config=None):
		from app.models.database_config import load as load_config
		self.config = config or load_config()
		self.db_type = self.config.get("type", "sqlite")
		self._connection = None

	def get_connection(self):
		if self.db_type == "mysql":
			return self._get_mysql_connection()
		else:
			return get_connection()

	def _get_mysql_connection(self):
		try:
			import pymysql
			mysql_cfg = self.config.get("mysql", {})
			conn = pymysql.connect(
				host=mysql_cfg.get("host", "localhost"),
				port=int(mysql_cfg.get("port", 3306)),
				user=mysql_cfg.get("user", "root"),
				password=mysql_cfg.get("password", ""),
				database=mysql_cfg.get("database", "cnagentos"),
				charset=mysql_cfg.get("charset", "utf8mb4"),
				cursorclass=pymysql.cursors.DictCursor
			)
			return MySQLConnectionWrapper(conn)
		except ImportError:
			raise RuntimeError("未安装pymysql库，请运行: pip install pymysql")
		except Exception as e:
			raise RuntimeError(f"MySQL连接失败: {e}")

	def test_connection(self):
		try:
			conn = self.get_connection()
			if self.db_type == "mysql":
				conn.execute("SELECT 1")
				conn.fetchone()
				conn.close()
			else:
				conn.execute("SELECT 1")
				conn.close()
			return True, "连接成功"
		except Exception as e:
			return False, str(e)

	def migrate_data(self, source_type, target_config):
		from app.models.database_config import load
		if source_type == "sqlite":
			source_config = {"type": "sqlite", "sqlite": {}}
		else:
			source_config = load()

		source_adapter = DatabaseAdapter(source_config)
		target_adapter = DatabaseAdapter(target_config)

		source_conn = source_adapter.get_connection()
		target_conn = target_adapter.get_connection()

		result = {"tables": [], "total_rows": 0, "errors": []}
		source_cur = None

		try:
			if source_type == "sqlite":
				tables = [row[0] for row in source_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
			else:
				source_cur = source_conn.cursor() if hasattr(source_conn, 'cursor') else source_conn._conn.cursor()
				source_cur.execute("SHOW TABLES")
				tables = [row[list(row.keys())[0]] for row in source_cur.fetchall()]

			skip_tables = ['alembic_version', 'migrations']

			for table_name in tables:
				if table_name in skip_tables:
					continue

				try:
					if source_type == "sqlite":
						rows = source_conn.execute(f"SELECT * FROM [{table_name}]").fetchall()
					else:
						if not source_cur:
							source_cur = source_conn.cursor() if hasattr(source_conn, 'cursor') else source_conn._conn.cursor()
						source_cur.execute(f"SELECT * FROM `{table_name}`")
						rows = source_cur.fetchall()

					row_count = len(rows) if rows else 0

					if row_count > 0:
						if target_config["type"] == "mysql":
							columns = list(rows[0].keys()) if isinstance(rows[0], dict) else rows[0].keys()
							placeholders = ", ".join(["%s"] * len(columns))
							column_names = ", ".join([f"`{col}`" for col in columns])
							insert_sql = f"INSERT INTO `{table_name}` ({column_names}) VALUES ({placeholders})"
							target_cur = target_conn.cursor() if hasattr(target_conn, 'cursor') else target_conn._conn.cursor()
							for row in rows:
								values = tuple(row[col] for col in columns) if isinstance(row, dict) else tuple(row)
								try:
									target_cur.execute(insert_sql.replace('INSERT INTO', 'INSERT IGNORE INTO'), values)
								except:
									pass
							target_conn._conn.commit() if hasattr(target_conn, '_conn') else None
						else:
							columns = list(rows[0].keys()) if isinstance(rows[0], dict) else rows[0].keys()
							placeholders = ", ".join(["?"] * len(columns))
							column_names = ", ".join([f"[{col}]" for col in columns])
							insert_sql = f"INSERT OR IGNORE INTO [{table_name}] ({column_names}) VALUES ({placeholders})"
							for row in rows:
								values = tuple(row[col] for col in columns) if isinstance(row, dict) else tuple(row)
								try:
									target_conn.execute(insert_sql, values)
								except:
									pass
							target_conn.commit() if hasattr(target_conn, 'commit') else None

					result["tables"].append({
						"name": table_name,
						"rows": row_count,
						"status": "success"
					})
					result["total_rows"] += row_count

				except Exception as e:
					result["tables"].append({
						"name": table_name,
						"rows": 0,
						"status": "error",
						"error": str(e)
					})
					result["errors"].append(f"{table_name}: {e}")

		finally:
			if source_cur and hasattr(source_cur, 'close'):
				source_cur.close()
			if source_type == "mysql" and source_conn:
				try:
					source_conn._conn.close()
				except:
					pass

		return True, result


_adapter_instance = None

def get_adapter(config=None):
	global _adapter_instance
	if _adapter_instance is None:
		_adapter_instance = DatabaseAdapter(config)
	return _adapter_instance

def reload_adapter(config=None):
	global _adapter_instance
	_adapter_instance = DatabaseAdapter(config)
	return _adapter_instance

