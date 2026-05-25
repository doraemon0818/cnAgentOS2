from app.models.db import init_db
from app.models.user import UserRepository

init_db()

print("创建默认管理员账号...")
result = UserRepository.create_user("admin", "admin888", email="admin@system.com", role="超级管理员")
print("管理员账号创建结果:", result)

print("创建测试用户...")
print("新增测试用户:", UserRepository.create_user("admin1", "123456"))

print("根据条件查询:", UserRepository.get_user_by_username("admin"))
print("登陆验证：", UserRepository.verify_user("admin", "admin888"))
