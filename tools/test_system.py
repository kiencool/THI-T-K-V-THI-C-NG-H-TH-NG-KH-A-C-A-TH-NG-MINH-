import unittest
import json
from server_final_fix import app

class SmartDoorTests(unittest.TestCase):
    def setUp(self):
        # Thiết lập Client để giả lập request tới server (Mocking)
        self.app = app.test_client()
        self.app.testing = True

    def test_login_admin_success(self):
        """Kiểm tra chức năng Đăng nhập Admin với mật khẩu đúng"""
        response = self.app.post('/api/login', json={"role": "admin", "password": "1"})
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["token"], "admin_token")

    def test_login_admin_fail(self):
        """Kiểm tra chức năng chặn Đăng nhập khi sai mật khẩu"""
        response = self.app.post('/api/login', json={"role": "admin", "password": "wrongpassword"})
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(data["status"], "error")

    def test_login_tenant_success(self):
        """Kiểm tra chức năng Đăng nhập Tenant"""
        response = self.app.post('/api/login', json={"role": "tenant", "password": "1"})
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")

    def test_missing_role(self):
        """Kiểm tra khi client gửi thiếu Role"""
        response = self.app.post('/api/login', json={"password": "1"})
        data = json.loads(response.data)
        # Mặc định role là admin
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")

if __name__ == '__main__':
    unittest.main(verbosity=2)
