from fastapi import FastAPI

downstream_app = FastAPI(title="Downstream Service")

@downstream_app.get("/hello")
async def hello():
    return{
        "message": "Hello from downstream service"
    }
    
    