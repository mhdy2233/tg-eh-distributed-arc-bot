from sqlalchemy import Column, Integer, String
from database import Base
from pydantic import BaseModel

class Record(Base):
    __tablename__ = "logs"  # 替换为你的表名

    id = Column(Integer, primary_key=True, index=True)
    title1 = Column(String(255))
    title2 = Column(String(255))
    image_url = Column(String(255))
    url = Column(String(255))

class GP(BaseModel):
    gp: int

# 定义接收的 JSON 表单数据模型
class Item(BaseModel):
    gid: str
    token: str
    clarity: str = "original"  # 可选字段