import json
import asyncio
import logging

import tornado.web

from app.controllers.base import BaseHandler
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.weather_image import generate_weather_image

logger = logging.getLogger(__name__)


class EmployeeOptionsHandler(BaseHandler):
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    @tornado.web.authenticated
    def get(self):
        self._write_json({"code": 0, "msg": "", "data": DigitalEmployeeRepository.get_employee_options()})


class EmployeeChatHandler(BaseHandler):
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    @tornado.web.authenticated
    async def post(self):
        message = (self.get_body_argument("message", "") or "").strip()
        if not message:
            self._write_json({"code": 1, "msg": "消息内容不能为空"})
            return
        try:
            result = await DigitalEmployeeRepository.chat_once(message)
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "employee": {
                        "name": result["employee"]["name"],
                        "alias": result["employee"]["alias"],
                        "category": result["employee"]["category"],
                    },
                    "content": result["content"],
                    "prompt_tokens": result.get("prompt_tokens", 0),
                    "completion_tokens": result.get("completion_tokens", 0),
                    "total_tokens": result.get("total_tokens", 0),
                    "response_ms": result.get("response_ms", 0),
                    "status_code": result.get("status_code", 200),
                    "content_type": result.get("content_type", ""),
                },
            })
        except Exception as exc:
            self._write_json({"code": 1, "msg": str(exc)})


class EmployeeStreamHandler(BaseHandler):
    @tornado.web.authenticated
    async def get(self):
        message = (self.get_argument("message", "") or "").strip()
        if not message:
            self.set_status(400)
            self.write("data: " + json.dumps({"type": "error", "message": "消息内容不能为空"}, ensure_ascii=False) + "\n\n")
            return

        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        await self.flush()

        try:
            async for item in DigitalEmployeeRepository.stream_chat(message):
                self.write("data: " + json.dumps(item, ensure_ascii=False) + "\n\n")
                await self.flush()
        except Exception as exc:
            self.write("data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n")
            await self.flush()


class WeatherImageHandler(BaseHandler):
    def check_xsrf_cookie(self):
        pass

    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    @tornado.web.authenticated
    async def post(self):
        try:
            body = json.loads(self.request.body.decode('utf-8'))
            city = body.get("city", "")
            weather_text = body.get("weather", "")
            spots = body.get("spots", [])
            if not city or not weather_text:
                self._write_json({"code": 1, "msg": "城市和天气信息不能为空"})
                return
            loop = asyncio.get_event_loop()
            image_url = await loop.run_in_executor(None, generate_weather_image, city, weather_text, spots)
            if image_url:
                self._write_json({"code": 0, "msg": "ok", "data": {"image_url": image_url}})
            else:
                self._write_json({"code": 1, "msg": "图像生成失败"})
        except Exception as exc:
            logger.error(f"Weather image generation error: {exc}")
            self._write_json({"code": 1, "msg": str(exc)})
