from fastapi import APIRouter,  HTTPException
from starlette.responses import JSONResponse
from schemas import Text
from inference import Inference

router = APIRouter()
inference = Inference()



@router.post('/predict')
async def predict_endpoint(request: Text):
    try:
        exported_model_output = inference(request.text)
        return JSONResponse(content={'predicted_tip': exported_model_output})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка предсказания: {str(e)}")