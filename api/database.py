from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 替换下面的内容为你的真实数据库配置
DATABASE_URL = "mysql+pymysql://root:pass@127.0.0.1:3306/eh_arc"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
