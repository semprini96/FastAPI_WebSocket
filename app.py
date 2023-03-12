import asyncio
from typing import Dict, List
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
import httpx


app = FastAPI()
URL = 'https://catfact.ninja/fact'
templates = Jinja2Templates(directory='.')

class APIData(BaseModel):
    fact: str = ''
    status: str = 'in_progress'

data = APIData()


class ConnectionManger:
    def __init__(self) -> None:
        self.connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    async def broadcast(self, b_data: str):
        for connection in self.connections:
            await connection.send_text(b_data)

    def remove(self, websocket: WebSocket):
        self.connections.remove(websocket)

manager = ConnectionManger()


async def background_task():
    while True:
        async with httpx.AsyncClient() as client:
            print('Requesting API...')
            try:
                resp = await client.get(URL)
                resp.raise_for_status()
                t_data = resp.text
                data.fact = t_data
                data.status = 'completed'
            except httpx.HTTPError as exc:
                data.status = 'error'
                print(f'HTTP exception: ', exc)
        
        print('Waiting 30 seconds...')
        await asyncio.sleep(30)


@app.on_event('startup')
async def schedule_periodic():
    loop = asyncio.get_event_loop()
    loop.create_task(background_task())


@app.websocket('/ws/{client_id}')
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    print(f'Accepted connection from client with ID={client_id})')
    await manager.connect(websocket)
    try:
        while True:
            print(f'Received ping from client with ID={client_id})')
            await websocket.receive_text()
            if data.status == 'completed':
                resp = data.fact
                data.status = 'await'
                await manager.broadcast(resp)
            elif data.status == 'in_progress':
                resp = 'Retrieving data, please wait...'
                await manager.broadcast(resp)
    except WebSocketDisconnect:
        print(f'Disconnected client with ID={client_id}')
        manager.remove(websocket)
    # print(f'Waiting 10 seconds for ping from client with ID={client_id}')
    # await asyncio.sleep(10)
    # print('Bye')


@app.get('/')
async def root(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})
