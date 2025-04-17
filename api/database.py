from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import yaml

with open("./config.yml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 替换下面的内容为你的真实数据库配置
DATABASE_URL = f"mysql+pymysql://{config['mysql']['user']}:{config['mysql']['password']}@{config['mysql']['host']}:{config['mysql']['port']}/{config['mysql']['db']}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
