from fastapi import FastAPI, Header

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
     