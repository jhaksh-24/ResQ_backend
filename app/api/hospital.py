from fastapi import APIRouter

hospital_router = APIRouter(
    prefix="/hospital",
    tags=["Hospital"]
)

@hospital_router.get("/recommended")
def get_hospital_recommended():
    return {
        "Recommended_Hospital": "Comming soon"
    }

@hospital_router.get("/list")
def get_hospital_list():
    return {
        "Hospital_list": []
    }