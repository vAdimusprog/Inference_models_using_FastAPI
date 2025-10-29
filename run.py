import uvicorn
from fastapi import FastAPI


from routers import router as inference_router

app = FastAPI()

app.include_router(inference_router)
#./venv/Scripts/activate
if __name__ == '__main__':
    print("🚀 Starting server on http://127.0.0.1:8000")
    print("📚 Documentation: http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)