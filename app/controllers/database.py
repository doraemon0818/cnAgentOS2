import json
import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.database_config import load, save as _save_config
from app.models.db import get_adapter, reload_adapter


class AdminDatabaseHandler(AdminBaseHandler):
	def check_xsrf_cookie(self):
		pass

	@tornado.web.authenticated
	def get(self):
		self.render("admin/database.html", title="数据库设置", username=self.current_user)


class DatabaseConfigHandler(AdminBaseHandler):
	def check_xsrf_cookie(self):
		pass

	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		config = load()
		adapter = get_adapter()
		self._write_json({
			"code": 0,
			"data": {
				"type": config.get("type", "sqlite"),
				"sqlite": config.get("sqlite", {}),
				"mysql": config.get("mysql", {})
			},
			"current_type": adapter.db_type
		})

	@tornado.web.authenticated
	def post(self):
		try:
			data = json.loads(self.request.body)
		except Exception:
			data = {}
		db_type = data.get("type", "sqlite")
		if db_type not in ("sqlite", "mysql"):
			self._write_json({"code": 1, "msg": "不支持的数据库类型"})
			return
		config = load()
		config["type"] = db_type
		if db_type == "mysql":
			mysql_cfg = data.get("mysql", {})
			config["mysql"] = {
				"host": mysql_cfg.get("host", "localhost"),
				"port": int(mysql_cfg.get("port", 3306)),
				"user": mysql_cfg.get("user", "root"),
				"password": mysql_cfg.get("password", ""),
				"database": mysql_cfg.get("database", "cnagentos"),
				"charset": mysql_cfg.get("charset", "utf8mb4")
			}
		_save_config(config)
		reload_adapter()
		self._write_json({"code": 0, "msg": "保存成功"})


class DatabaseTestHandler(AdminBaseHandler):
	def check_xsrf_cookie(self):
		pass

	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def post(self):
		try:
			data = json.loads(self.request.body)
		except Exception:
			data = {}
		db_type = data.get("type", "sqlite")
		test_config = {
			"type": db_type,
			"sqlite": data.get("sqlite", {}),
			"mysql": data.get("mysql", {})
		}
		from app.models.db import DatabaseAdapter
		adapter = DatabaseAdapter(test_config)
		ok, msg = adapter.test_connection()
		if ok:
			self._write_json({"code": 0, "msg": msg})
		else:
			self._write_json({"code": 1, "msg": msg})


class DatabaseMigrateHandler(AdminBaseHandler):
	def check_xsrf_cookie(self):
		pass

	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def post(self):
		try:
			data = json.loads(self.request.body)
		except Exception:
			data = {}
		target_type = data.get("target_type", "mysql")
		source_type = data.get("source_type", None)
		if target_type not in ("sqlite", "mysql"):
			self._write_json({"code": 1, "msg": "不支持的数据库类型"})
			return
		if not source_type:
			current_adapter = get_adapter()
			source_type = current_adapter.db_type
		if source_type == target_type:
			self._write_json({"code": 1, "msg": "源数据库和目标数据库相同，无需迁移"})
			return
		from app.models.db import DatabaseAdapter
		if target_type == "mysql":
			mysql_cfg = data.get("mysql", {})
			target_config = {
				"type": "mysql",
				"mysql": {
					"host": mysql_cfg.get("host", "localhost"),
					"port": int(mysql_cfg.get("port", 3306)),
					"user": mysql_cfg.get("user", "root"),
					"password": mysql_cfg.get("password", ""),
					"database": mysql_cfg.get("database", "cnagentos"),
					"charset": mysql_cfg.get("charset", "utf8mb4")
				}
			}
		else:
			target_config = {"type": "sqlite", "sqlite": {}}
		adapter = DatabaseAdapter()
		ok, result = adapter.migrate_data(source_type, target_config)
		if ok:
			success_count = sum(1 for t in result["tables"] if t["status"] == "成功")
			skip_count = sum(1 for t in result["tables"] if "跳过" in t["status"])
			error_count = len(result["errors"])
			msg = f"迁移完成！共 {len(result['tables'])} 张表，{success_count} 张成功，{skip_count} 张跳过，{error_count} 张失败，总计 {result['total_rows']} 条数据"
			self._write_json({
				"code": 0,
				"msg": msg,
				"data": {
					"tables": result["tables"],
					"total_rows": result["total_rows"],
					"errors": result["errors"]
				}
			})
		else:
			self._write_json({"code": 1, "msg": "迁移失败", "data": {"errors": [str(result)]}})
