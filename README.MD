uv run uvicorn app.main:app --host localhost --port 8000 --reload

正常数据：
{
  "transaction_id": "txn_test_normal_001",
  "uid": "player_001",
  "amount": 30.00,
  "device_id": "dev_005",
  "ip": "192.168.1.10",
  "payment_method": "wechat"
}

异常数据：
