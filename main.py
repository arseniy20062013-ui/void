import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="VOID Hybrid Server")

# Настройка доступа для твоего домена
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- БАЗА ДАННЫХ В ПАМЯТИ ---
users_db = []
active_connections: List[WebSocket] = []

class UserSchema(BaseModel):
    username: str
    password: str

# --- ЛОГИКА БАЛАНСИРОВКИ ---
def get_server_load_config():
    user_count = len(active_connections)
    # Порог мощности: если людей > 10, сервер уходит в эконом-режим
    if user_count > 10:
        return {
            "mode": "CLIENT_POWER", 
            "description": "Server busy. Client handles heavy UI and encryption.",
            "power_ratio": "20/80"
        }
    else:
        return {
            "mode": "SERVER_POWER", 
            "description": "Server stable. High-quality processing enabled.",
            "power_ratio": "80/20"
        }

# --- API ЭНДПОИНТЫ ---
@app.post("/api/register")
async def register(user: UserSchema):
    if any(u['username'] == user.username for u in users_db):
        raise HTTPException(status_code=400, detail="User exists")
    users_db.append(user.dict())
    return {"status": "success", "message": f"Welcome to VOID, {user.username}"}

@app.post("/api/login")
async def login(user: UserSchema):
    for u in users_db:
        if u['username'] == user.username and u['password'] == user.password:
            return {"status": "success", "token": "void_secret_key"}
    raise HTTPException(status_code=401, detail="Wrong credentials")

# --- WEBSOCKET И ГИБРИДНАЯ МОЩЬ ---
@app.websocket("/ws/void")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    # Сразу при подключении отправляем клиенту его задачу по нагрузке
    load_config = get_server_load_config()
    await websocket.send_text(json.dumps({
        "type": "SYSTEM_INIT",
        "config": load_config,
        "online": len(active_connections)
    }))

    try:
        while True:
            # Получаем сообщение от пользователя
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Рассылаем всем остальным
            for connection in active_connections:
                await connection.send_text(json.dumps({
                    "type": "MESSAGE",
                    "user": message_data.get("user", "Anonymous"),
                    "text": message_data.get("text", ""),
                    "load_info": get_server_load_config() # Актуальный баланс сил
                }))
    except WebSocketDisconnect:
        active_connections.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    # Порт 7066 как в твоем vite.config.ts
    uvicorn.run(app, host="0.0.0.0", port=7066)