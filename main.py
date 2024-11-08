from fastapi import FastAPI, WebSocket, Request, Depends, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import uuid

docker_ip = "db"
docker_port = 5432

DATABASE_URL = "postgresql+psycopg2://shureck:787898QWEqwe@db:5432/biji"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

app = FastAPI()

# Модель для сообщений
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    content = Column(Text)

Base.metadata.create_all(engine)

# Хранилище для активных WebSocket соединений
active_connections = []

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def get(request: Request, username: str = Cookie(None)):
    if not username:
        return RedirectResponse("/login")
    return HTMLResponse(
        content=open("templates/index.html").read(),
        headers={"Set-Cookie": f"username={username}; Path=/; HttpOnly"},
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(content=open("templates/login.html").read())

@app.post("/login")
async def login(username: str = Form(...)):
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="username", value=username, httponly=True)
    return response

@app.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("username")
    return response

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db), username: str = Cookie(None)):
    if not username:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    active_connections.append(websocket)

    # Отправляем старые сообщения из БД
    messages = db.query(Message).all()
    for message in messages:
        await websocket.send_json({"username": message.username, "content": message.content})

    try:
        while True:
            data = await websocket.receive_json()
            message = Message(username=username, content=data["content"])
            db.add(message)
            db.commit()
            db.refresh(message)

            # Рассылаем сообщение всем активным соединениям
            for connection in active_connections:
                await connection.send_json({"username": username, "content": message.content})
    except:
        pass
    finally:
        active_connections.remove(websocket)
