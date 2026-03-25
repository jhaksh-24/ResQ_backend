from fastapi import APIRouter

dispatch_router = APIRouter(
    prefix="/dispatch",
    tags=["Dispatch"]
)

@dispatch_router.post("/request")
def dispatch_request():
    return {
        "message": "Dispatch endpoint not yet implemented"
    }

@dispatch_router.get("/history")
def dispatch_history():
    return {
        "message": "To be implemented",
        "dispatches": []
    }