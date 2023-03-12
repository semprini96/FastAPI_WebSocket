import asyncio
from typing import Dict
from fastapi import FastAPI, Request, WebSocket
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


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    print('Accepting client connection...')
    await websocket.accept()
    while True:
        try:
            print('Received ping from client...')
            await websocket.receive_text()
            if data.status == 'completed':
                resp = data.fact
                data.status = 'await'
                await websocket.send_text(resp)
            elif data.status == 'in_progress':
                resp = 'Retrieving data, please wait...'
                await websocket.send_text(resp)
        except Exception as e:
            print('ERROR: ', e)
            break
        print('Waiting 10 seconds for ping...')
        await asyncio.sleep(10)
    print('Bye')


@app.get('/')
async def root(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})
