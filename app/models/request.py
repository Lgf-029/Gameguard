from pydantic import BaseModel, Field
from decimal import Decimal

class DetectRequest(BaseModel):
    transaction_id: str = Field(..., description="交易唯一ID")
    uid: str = Field(..., description="玩家ID")
    amount: Decimal = Field(..., description="交易金额")
    device_id: str = Field(..., description="设备指纹")
    ip: str = Field(..., description="客户端IP")
    payment_method: str = Field(..., description="支付方式")

