# import time
# from datetime import datetime
# import os
# from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, create_engine, ForeignKeyConstraint, \
#     UniqueConstraint, exc, and_, desc, Boolean
# from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Base = declarative_base()

# docker_ip = "db"
# docker_port = 5432

# class User(Base):
#     __tablename__ = 'user'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     token = Column(String(100), unique=True, nullable=False)
#     username = Column(String(100), nullable=False, default=None)
#     last_seen = Column(DateTime, nullable=False, default=None)
#     img_url = Column(String(100), default=None)

# engine = create_engine(f"postgresql+psycopg2://shureck:787898QWEqwe@{docker_ip}:{docker_port}/biji")
# Base.metadata.create_all(engine)
# Session = sessionmaker(bind=engine)

# User.__table__.drop(engine)
# Base.metadata.create_all(engine)

# def add_new_user(username: str, token: str, img_url:str = None):
#     session = Session()
#     scene = User(username=username, token=token, last_seen=datetime.now(), img_url=img_url)
#     session.add(scene)
#     session.commit()


# def get_user(username:str):
#     session = Session(expire_on_commit=False)
#     print(username)
#     user = session.query(User).filter(User.username == username).first()
#     if user is None:
#         return ''
#     print(user)
#     return user