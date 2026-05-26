import copy
import json
import re
from typing import Dict, Optional

from app.models.api_endpoint import ApiEndpointRepository
from app.models.db import get_connection
from app.models.model_engine import ModelEngineClient, ModelEngineRepository


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _flatten_data(value, prefix="", result=None):
    if result is None:
        result = {}
    if isinstance(value, dict):
        for key, item in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_data(item, new_prefix, result)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            new_prefix = f"{prefix}.{index}" if prefix else str(index)
            _flatten_data(item, new_prefix, result)
    else:
        result[prefix] = value if value is not None else ""
    return result


def _render_template(template: str, payload):
    if not template:
        if isinstance(payload, (dict, list)):
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return str(payload or "")

    flat_map = _flatten_data(payload)
    content = template
    for key, value in flat_map.items():
        content = content.replace("{" + key + "}", str(value))
    content = re.sub(r"\{[^{}]+\}", "", content)
    return content.strip()


class DigitalEmployeeRepository:
    EMPLOYEE_AI = "AI"
    EMPLOYEE_NORMAL = "普通"
    AT_PATTERN = re.compile(r"^\s*@([^\s：:]+)\s*[：:]?\s*(.*)$", re.S)

    @staticmethod
    def _row_to_dict(row):
        if not row:
            return None
        data = dict(row)
        data["api_params"] = _safe_json_loads(data.get("api_params_json"), {})
        return data

    @staticmethod
    def get_employee_list(page=1, page_size=20, keyword=""):
        offset = (page - 1) * page_size
        params = []
        where_sql = ""
        if keyword:
            like_value = f"%{keyword}%"
            where_sql = """
                where de.name like ? or de.alias like ? or de.code like ? or de.description like ?
            """
            params.extend([like_value, like_value, like_value, like_value])

        sql = f"""
            select de.id,de.name,de.alias,de.code,de.category,de.model_id,de.endpoint_id,
                   de.prompt,de.api_param_name,de.api_params_json,de.response_template,
                   de.default_user_input,de.description,de.sort,de.status,de.create_at,de.update_at,
                   ms.name as model_name,
                   ae.name as endpoint_name
            from digital_employees de
            left join model_services ms on ms.id = de.model_id
            left join api_endpoints ae on ae.id = de.endpoint_id
            {where_sql}
            order by de.sort asc,de.id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from digital_employees de {where_sql}"
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        return {"list": [DigitalEmployeeRepository._row_to_dict(row) for row in rows], "total": total}

    @staticmethod
    def get_employee_by_id(employee_id: int):
        with get_connection() as conn:
            row = conn.execute(
                """
                select de.*, ms.name as model_name, ae.name as endpoint_name
                from digital_employees de
                left join model_services ms on ms.id = de.model_id
                left join api_endpoints ae on ae.id = de.endpoint_id
                where de.id=?
                """,
                (employee_id,),
            ).fetchone()
        return DigitalEmployeeRepository._row_to_dict(row)

    @staticmethod
    def get_employee_by_alias(alias: str):
        with get_connection() as conn:
            row = conn.execute(
                """
                select de.*, ms.name as model_name, ae.name as endpoint_name
                from digital_employees de
                left join model_services ms on ms.id = de.model_id
                left join api_endpoints ae on ae.id = de.endpoint_id
                where de.alias=? and de.status=1
                limit 1
                """,
                ((alias or "").strip(),),
            ).fetchone()
        return DigitalEmployeeRepository._row_to_dict(row)

    @staticmethod
    def get_employee_options():
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,name,alias,code,category,description,default_user_input,api_param_name
                from digital_employees
                where status=1
                order by sort asc,id asc
                """
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def save_employee(data: Dict, employee_id: Optional[int] = None):
        name = (data.get("name") or "").strip()
        alias = (data.get("alias") or "").strip()
        code = (data.get("code") or "").strip()
        category = (data.get("category") or DigitalEmployeeRepository.EMPLOYEE_AI).strip()
        prompt = (data.get("prompt") or "").strip()
        api_param_name = (data.get("api_param_name") or "").strip()
        api_params_json = (data.get("api_params_json") or "{}").strip() or "{}"
        response_template = (data.get("response_template") or "").strip()
        default_user_input = (data.get("default_user_input") or "").strip()
        description = (data.get("description") or "").strip()
        sort = int(data.get("sort") or 0)
        status = int(data.get("status") or 1)

        if not name or not alias or not code:
            return False, "员工名称、别名、编码不能为空"
        if category not in (DigitalEmployeeRepository.EMPLOYEE_AI, DigitalEmployeeRepository.EMPLOYEE_NORMAL):
            return False, "员工分类不正确"

        try:
            json.loads(api_params_json)
        except json.JSONDecodeError:
            return False, "默认参数JSON格式不正确"

        model_id = data.get("model_id")
        endpoint_id = data.get("endpoint_id")
        model_id = int(model_id) if str(model_id or "").strip() else None
        endpoint_id = int(endpoint_id) if str(endpoint_id or "").strip() else None

        if category == DigitalEmployeeRepository.EMPLOYEE_NORMAL and not endpoint_id:
            return False, "普通员工必须绑定接口服务"

        with get_connection() as conn:
            duplicate_sql = "select id from digital_employees where (name=? or alias=? or code=?)"
            duplicate_params = [name, alias, code]
            if employee_id:
                duplicate_sql += " and id<>?"
                duplicate_params.append(employee_id)
            duplicate = conn.execute(duplicate_sql, tuple(duplicate_params)).fetchone()
            if duplicate:
                return False, "员工名称、别名或编码已存在"

            if model_id:
                model_row = conn.execute("select id from model_services where id=?", (model_id,)).fetchone()
                if not model_row:
                    return False, "绑定模型不存在"
            if endpoint_id:
                endpoint_row = conn.execute("select id from api_endpoints where id=?", (endpoint_id,)).fetchone()
                if not endpoint_row:
                    return False, "绑定接口不存在"

            payload = (
                name,
                alias,
                code,
                category,
                model_id if category == DigitalEmployeeRepository.EMPLOYEE_AI else None,
                endpoint_id if category == DigitalEmployeeRepository.EMPLOYEE_NORMAL else None,
                prompt if category == DigitalEmployeeRepository.EMPLOYEE_AI else "",
                api_param_name if category == DigitalEmployeeRepository.EMPLOYEE_NORMAL else "",
                api_params_json,
                response_template if category == DigitalEmployeeRepository.EMPLOYEE_NORMAL else "",
                default_user_input,
                description,
                sort,
                status,
            )

            if employee_id:
                conn.execute(
                    """
                    update digital_employees
                    set name=?,alias=?,code=?,category=?,model_id=?,endpoint_id=?,prompt=?,api_param_name=?,
                        api_params_json=?,response_template=?,default_user_input=?,description=?,sort=?,status=?,
                        update_at=datetime('now','localtime')
                    where id=?
                    """,
                    payload + (employee_id,),
                )
            else:
                conn.execute(
                    """
                    insert into digital_employees(
                        name,alias,code,category,model_id,endpoint_id,prompt,api_param_name,api_params_json,
                        response_template,default_user_input,description,sort,status,create_at,update_at
                    ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
                    """,
                    payload,
                )
        return True, "保存成功"

    @staticmethod
    def delete_employee(employee_id: int):
        with get_connection() as conn:
            conn.execute("delete from digital_employees where id=?", (employee_id,))
        return True, "删除成功"

    @staticmethod
    def parse_at_message(message: str):
        match = DigitalEmployeeRepository.AT_PATTERN.match((message or "").strip())
        if not match:
            return None
        return {"alias": match.group(1).strip(), "content": (match.group(2) or "").strip()}

    @staticmethod
    def _get_employee_request_text(employee: Dict, user_text: str):
        text = (user_text or "").strip()
        return text or (employee.get("default_user_input") or "").strip()

    @staticmethod
    def _resolve_model_config(employee: Dict):
        if employee.get("model_id"):
            config = ModelEngineRepository.get_model_by_id(int(employee["model_id"]), include_secret=True)
        else:
            config = ModelEngineRepository.get_default_model(include_secret=True)
            if not config:
                config = ModelEngineRepository.get_first_active_model(include_secret=True)
        if not config:
            raise RuntimeError("当前数字员工未绑定模型，且系统中暂无启用模型，请先到模型引擎中启用一个模型或设为默认模型")
        config = copy.deepcopy(config)
        prompts = []
        if config.get("system_prompt"):
            prompts.append(config["system_prompt"])
        if employee.get("prompt"):
            prompts.append(employee["prompt"])
        config["system_prompt"] = "\n\n".join([item for item in prompts if item]).strip()
        return config

    @staticmethod
    def _resolve_api_content(employee: Dict, user_text: str):
        endpoint_id = int(employee.get("endpoint_id") or 0)
        endpoint = ApiEndpointRepository.get_endpoint_by_id(endpoint_id)
        if not endpoint:
            raise RuntimeError("当前数字员工绑定的接口不存在")

        params = _safe_json_loads(employee.get("api_params_json"), {})
        request_text = DigitalEmployeeRepository._get_employee_request_text(employee, user_text)
        param_name = (employee.get("api_param_name") or "").strip()
        is_music = "音乐" in employee.get("alias", "") or "音乐" in employee.get("name", "")
        
        if is_music and request_text and param_name:
            keyword = DigitalEmployeeRepository._extract_music_keyword(request_text)
            params[param_name] = keyword
        elif param_name and request_text:
            params[param_name] = request_text
        elif param_name and not request_text and employee.get("default_user_input"):
            params[param_name] = employee.get("default_user_input")
            
        if param_name and not params.get(param_name):
            raise RuntimeError(f"请使用 @{employee['alias']} 后补充参数内容")

        if is_music:
            params.setdefault("limit", "30")

        result = ApiEndpointRepository.call_endpoint(endpoint, params=params)
        payload = result.get("json") if result.get("json") is not None else {"text": result.get("text", "")}
        
        if is_music:
            keyword = DigitalEmployeeRepository._extract_music_keyword(request_text) if request_text else "热歌"
            payload = DigitalEmployeeRepository._normalize_music_payload(payload, keyword)
        
        content = _render_template(employee.get("response_template") or "", payload)
        if not content:
            content = json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            "content": content,
            "payload": payload,
            "status_code": result.get("status_code"),
            "content_type": result.get("content_type"),
        }

    @staticmethod
    def _extract_music_keyword(text: str) -> str:
        """从用户输入中提取音乐搜索关键词"""
        text = (text or "").strip()
        if not text:
            return "热歌"
        
        # 移除常见的前缀词
        prefixes = ["来首", "播放", "听", "找", "搜索", "查找"]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        
        # 移除后缀词
        suffixes = ["的歌", "的歌曲", "的音乐", "的歌单", "歌", "歌曲", "音乐"]
        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[:-len(suffix)].strip()
                break
        
        # 如果处理后为空，返回热歌作为默认关键词
        if not text:
            return "热歌"

        return text

    @staticmethod
    def _filter_music_by_keyword(data: list, keyword: str) -> list:
        if not keyword or not data:
            return data
        
        kw = keyword.lower().strip()
        japanese_re = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')
        korean_re = re.compile(r'[\uac00-\ud7af]')
        
        lang_map = {"日语": "ja", "日文": "ja", "日本": "ja", "韩语": "ko", "韩文": "ko", "韩国": "ko", "英语": "en", "英文": "en"}
        lang = lang_map.get(kw)
        
        if lang:
            def lang_match(item):
                song = (item.get("song") or "").lower()
                singer = (item.get("singer") or item.get("sing") or "").lower()
                combined = song + " " + singer
                if lang == "ja":
                    return bool(japanese_re.search(combined))
                elif lang == "ko":
                    return bool(korean_re.search(combined))
                elif lang == "en":
                    has_ascii = bool(re.search(r'[a-zA-Z]', combined))
                    no_cjk = not bool(re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', combined))
                    return has_ascii and no_cjk
                return True
            filtered = [item for item in data if lang_match(item)]
            if filtered:
                return filtered
            return data
        
        result = []
        for item in data:
            song = (item.get("song") or "").lower()
            singer = (item.get("singer") or item.get("sing") or "").lower()
            if kw in song or kw in singer:
                result.append(item)
        return result if result else data

    @staticmethod
    def _refresh_music_cover(song_id: int, existing_cover: str = "") -> str:
        """通过网易云音乐API刷新歌曲封面URL"""
        if not song_id or not str(song_id).isdigit():
            return existing_cover
        try:
            import requests
            url = f"https://music.163.com/api/song/detail?id={song_id}&ids=[{song_id}]"
            headers = {
                "Referer": "https://music.163.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": "appver=2.0.2"
            }
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                songs = data.get("songs", [])
                if songs and isinstance(songs, list):
                    album = songs[0].get("album") or {}
                    new_cover = album.get("picUrl") or album.get("pic_url") or album.get("coverImgUrl") or ""
                    if new_cover:
                        print(f"[MusicCover] Refreshed cover for song {song_id}: {new_cover[:60]}...")
                        return new_cover
        except Exception as e:
            print(f"[MusicCover] Failed to refresh cover for song {song_id}: {e}")
        return existing_cover

    @staticmethod
    def _normalize_music_payload(payload: Dict, keyword: str = None) -> Dict:
        """标准化音乐API返回的数据格式，支持按关键词本地过滤"""
        if not isinstance(payload, dict):
            return payload
        
        search_result = payload.get("result")
        if isinstance(search_result, dict) and "songs" in search_result:
            songs = search_result.get("songs") or []
            free_songs = [s for s in songs if s.get("fee") in (0, 8)]

            def _search_norm(s):
                s_id = s.get("id")
                artists = [_a.get("name", "") for _a in (s.get("artists") or s.get("ar") or []) if _a.get("name")]
                album = s.get("album") or s.get("al") or {}
                cover = album.get("picUrl") or ""
                if not cover and s.get("artists"):
                    first_artist = s["artists"][0] if isinstance(s["artists"], list) and s["artists"] else {}
                    cover = first_artist.get("img1v1Url") or ""
                if not cover and s.get("ar"):
                    first_artist = s["ar"][0] if isinstance(s["ar"], list) and s["ar"] else {}
                    cover = first_artist.get("img1v1Url") or ""
                if not cover:
                    cover = album.get("pic_url") or album.get("coverImgUrl") or ""
                cover = DigitalEmployeeRepository._refresh_music_cover(s_id, cover)
                return {
                    "song": s.get("name") or "未知歌曲",
                    "singer": " / ".join(artists) if artists else "未知歌手",
                    "music": f"https://music.163.com/song/media/outer/url?id={s_id}.mp3" if s_id else "",
                    "cover": cover,
                }

            playlist = [_search_norm(s) for s in free_songs]

            if keyword and keyword != "random" and keyword != "热歌":
                playlist = DigitalEmployeeRepository._filter_music_by_keyword(playlist, keyword)

            normalized = {
                "song": playlist[0]["song"] if playlist else "未知歌曲",
                "singer": playlist[0]["singer"] if playlist else "未知歌手",
                "music": playlist[0]["music"] if playlist else "",
                "cover": playlist[0]["cover"] if playlist else "",
                "source": "网易云音乐搜索",
                "playlist": playlist,
                "current_index": 0,
                "songCount": search_result.get("songCount", len(songs)),
                "freeCount": len(free_songs),
            }
            if "data" in payload:
                payload["data"] = normalized
            else:
                payload.update(normalized)
            return payload
        
        data = payload.get("data")
        if data is None and isinstance(payload, dict) and any(k in payload for k in ("song", "singer", "Music", "music")):
            data = payload
        
        def _normalize_item(item):
            if not isinstance(item, dict):
                return None
            return {
                "song": item.get("song") or item.get("name") or item.get("title") or "未知歌曲",
                "singer": item.get("singer") or item.get("artist") or item.get("author") or item.get("sing") or "未知歌手",
                "music": item.get("music") or item.get("Music") or item.get("url") or item.get("audio") or item.get("play_url") or "",
                "cover": item.get("cover") or item.get("pic") or item.get("image") or item.get("poster") or "",
            }
        
        if isinstance(data, dict):
            if "Music" in data and "music" not in data:
                data["music"] = data["Music"]
            
            normalized = {
                "song": data.get("song") or data.get("name") or data.get("title") or "未知歌曲",
                "singer": data.get("singer") or data.get("artist") or data.get("author") or data.get("sing") or "未知歌手",
                "music": data.get("music") or data.get("Music") or data.get("url") or data.get("audio") or data.get("play_url") or "",
                "cover": data.get("cover") or data.get("pic") or data.get("image") or data.get("poster") or "",
                "source": data.get("source") or data.get("platform") or data.get("from") or "音乐",
            }
            
            playlist = data.get("playlist") or data.get("playlist_data") or []
            if isinstance(playlist, list) and len(playlist) > 0:
                normalized_playlist = [_normalize_item(item) for item in playlist]
                normalized_playlist = [item for item in normalized_playlist if item is not None]
                
                if keyword and keyword != "random" and keyword != "热歌":
                    normalized_playlist = DigitalEmployeeRepository._filter_music_by_keyword(normalized_playlist, keyword)
                
                normalized["playlist"] = normalized_playlist
                normalized["current_index"] = data.get("current_index") or 0
                
                if normalized_playlist:
                    normalized["song"] = normalized_playlist[0]["song"]
                    normalized["singer"] = normalized_playlist[0]["singer"]
                    normalized["music"] = normalized_playlist[0]["music"]
                    normalized["cover"] = normalized_playlist[0]["cover"]
            
            if "data" in payload:
                payload["data"] = normalized
            else:
                payload.update(normalized)
        elif isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                normalized_playlist = [_normalize_item(item) for item in data]
                normalized_playlist = [item for item in normalized_playlist if item is not None]
                
                if keyword and keyword != "random" and keyword != "热歌":
                    normalized_playlist = DigitalEmployeeRepository._filter_music_by_keyword(normalized_playlist, keyword)
                
                first_item = normalized_playlist[0] if normalized_playlist else _normalize_item(data[0])
                normalized = {
                    "song": first_item.get("song") or "未知歌曲",
                    "singer": first_item.get("singer") or "未知歌手",
                    "music": first_item.get("music") or "",
                    "cover": first_item.get("cover") or "",
                    "source": first_item.get("source") or first_item.get("platform") or first_item.get("from") or "音乐",
                    "playlist": normalized_playlist,
                    "current_index": 0,
                }
                if "data" in payload:
                    payload["data"] = normalized
                else:
                    payload.update(normalized)
        
        return payload

    @staticmethod
    async def chat_once(message: str):
        parsed = DigitalEmployeeRepository.parse_at_message(message)
        if not parsed:
            raise RuntimeError("请使用 @数字员工别名 进行调用，例如：@天气 北京市")

        employee = DigitalEmployeeRepository.get_employee_by_alias(parsed["alias"])
        if not employee:
            raise RuntimeError(f"未找到别名为 @{parsed['alias']} 的数字员工")

        user_text = parsed["content"]
        if employee["category"] == DigitalEmployeeRepository.EMPLOYEE_AI:
            request_text = DigitalEmployeeRepository._get_employee_request_text(employee, user_text)
            if not request_text:
                raise RuntimeError(f"请在 @{employee['alias']} 后输入问题内容")
            config = DigitalEmployeeRepository._resolve_model_config(employee)
            try:
                result = await ModelEngineClient.chat_once(config, request_text)
                ModelEngineRepository.log_usage(
                    model_id=config["id"],
                    model_name=config["name"],
                    request_preview=request_text,
                    response_preview=result["content"],
                    prompt_tokens=result["prompt_tokens"],
                    completion_tokens=result["completion_tokens"],
                    total_tokens=result["total_tokens"],
                    response_ms=result["response_ms"],
                    success=1,
                )
                return {
                    "employee": employee,
                    "category": employee["category"],
                    "content": result["content"],
                    "prompt_tokens": result["prompt_tokens"],
                    "completion_tokens": result["completion_tokens"],
                    "total_tokens": result["total_tokens"],
                    "response_ms": result["response_ms"],
                }
            except Exception as exc:
                ModelEngineRepository.log_usage(
                    model_id=config["id"],
                    model_name=config["name"],
                    request_preview=request_text,
                    response_preview="",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    response_ms=0,
                    success=0,
                    error_message=str(exc),
                )
                raise

        api_result = DigitalEmployeeRepository._resolve_api_content(employee, user_text)
        weather_card = None
        music_card = None
        payload = api_result["payload"]
        if isinstance(payload, dict) and ("天气" in employee.get("alias", "") or "天气" in employee.get("name", "")):
            weather_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            if isinstance(weather_payload, dict):
                weather_card = weather_payload
                if "city" not in weather_card and user_text:
                    weather_card["city"] = user_text.strip()
        if isinstance(payload, dict) and ("音乐" in employee.get("alias", "") or "音乐" in employee.get("name", "")):
            music_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            if isinstance(music_payload, dict):
                music_card = music_payload
        return {
            "employee": employee,
            "category": employee["category"],
            "content": api_result["content"],
            "payload": payload,
            "weather_card": weather_card,
            "music_card": music_card,
            "status_code": api_result["status_code"],
            "content_type": api_result["content_type"],
        }

    @staticmethod
    async def stream_chat(message: str):
        parsed = DigitalEmployeeRepository.parse_at_message(message)
        if not parsed:
            raise RuntimeError("请使用 @数字员工别名 进行调用，例如：@天气 北京市")

        employee = DigitalEmployeeRepository.get_employee_by_alias(parsed["alias"])
        if not employee:
            raise RuntimeError(f"未找到别名为 @{parsed['alias']} 的数字员工")

        user_text = parsed["content"]
        if employee["category"] == DigitalEmployeeRepository.EMPLOYEE_AI:
            request_text = DigitalEmployeeRepository._get_employee_request_text(employee, user_text)
            if not request_text:
                raise RuntimeError(f"请在 @{employee['alias']} 后输入问题内容")
            config = DigitalEmployeeRepository._resolve_model_config(employee)
            try:
                async for item in ModelEngineClient.stream_chat(config, request_text):
                    if item["type"] == "delta":
                        yield {
                            "type": "delta",
                            "employee": {"name": employee["name"], "alias": employee["alias"], "category": employee["category"]},
                            "content": item["content"],
                        }
                    elif item["type"] == "done":
                        ModelEngineRepository.log_usage(
                            model_id=config["id"],
                            model_name=config["name"],
                            request_preview=request_text,
                            response_preview=item["content"],
                            prompt_tokens=item["prompt_tokens"],
                            completion_tokens=item["completion_tokens"],
                            total_tokens=item["total_tokens"],
                            response_ms=item["response_ms"],
                            success=1,
                        )
                        yield {
                            "type": "done",
                            "employee": {"name": employee["name"], "alias": employee["alias"], "category": employee["category"]},
                            "content": item["content"],
                            "prompt_tokens": item["prompt_tokens"],
                            "completion_tokens": item["completion_tokens"],
                            "total_tokens": item["total_tokens"],
                            "response_ms": item["response_ms"],
                        }
            except Exception as exc:
                ModelEngineRepository.log_usage(
                    model_id=config["id"],
                    model_name=config["name"],
                    request_preview=request_text,
                    response_preview="",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    response_ms=0,
                    success=0,
                    error_message=str(exc),
                )
                raise
            return

        api_result = DigitalEmployeeRepository._resolve_api_content(employee, user_text)
        weather_card = None
        music_card = None
        payload = api_result["payload"]
        if isinstance(payload, dict) and ("天气" in employee.get("alias", "") or "天气" in employee.get("name", "")):
            weather_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            if isinstance(weather_payload, dict):
                weather_card = weather_payload
                if "city" not in weather_card and user_text:
                    weather_card["city"] = user_text.strip()
        if isinstance(payload, dict) and ("音乐" in employee.get("alias", "") or "音乐" in employee.get("name", "")):
            music_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            if isinstance(music_payload, dict):
                music_card = music_payload
        yield {
            "type": "done",
            "employee": {"name": employee["name"], "alias": employee["alias"], "category": employee["category"]},
            "content": api_result["content"],
            "payload": payload,
            "weather_card": weather_card,
            "music_card": music_card,
            "status_code": api_result["status_code"],
            "content_type": api_result["content_type"],
        }
