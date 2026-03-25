from fastapi import FastAPI

app = FastAPI(title="ResQ Backend",
              description="built to move faster than tragedy",
              version="0.1.0 beta")

@app.get("/")
def root():
    return {
        "Message": "Welcome to ResQ backend",
        "version": "0.1.0 beta"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}