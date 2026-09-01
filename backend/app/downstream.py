from fastapi import FastAPI, Header
import asyncio

downstream_app = FastAPI(title="Downstream Service")

@downstream_app.get("/hello")
async def hello(name: str = "world"):
    return{
        "message": f"Hello, {name}!"
    }
    
@downstream_app.post("/echo")
async def echo(
    data: dict,
    x_client_name: str | None=Header(default=None),
    x_api_key: str | None= Header(default=None)
    ):
    
     return{
        "received": data,
        "client_name": x_client_name,
        "api_key_received": x_api_key
    }
@downstream_app.put("/echo")
async def update_echo(data: dict):
    return{
        "updated": data
    }
@downstream_app.patch("/echo")
async def patch_echo(data: dict):
    return{
        "patched": data   
        }
@downstream_app.delete("/echo")
async def delete_echo():
    return {
        "message": "Resource deleted"
    }

@downstream_app.get("/slow")
async def slow():
    await asyncio.sleep(15)
    return{
        "message": "Slow response"
    }
        