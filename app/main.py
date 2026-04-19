import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import BriefOutput, DossierRequest, PlaybookOutput
from app.services.crustdata import CrustdataError
from app.services.dossier import DossierError, build_brief, build_playbook
from app.services.synth import synthesize_brief, synthesize_playbook

logger = logging.getLogger("insiderbrief")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="InsiderBrief", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://agastya.pages.dev",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

_TIMEOUT_SECONDS = 180.0


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/brief", response_model=BriefOutput)
async def brief(req: DossierRequest) -> BriefOutput:
    try:
        async with asyncio.timeout(_TIMEOUT_SECONDS):
            raw = await build_brief(req.company, req.role)
            return await synthesize_brief(raw, req.role)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Dossier assembly timed out.")
    except DossierError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CrustdataError as e:
        logger.exception("Crustdata error")
        raise HTTPException(status_code=502, detail=f"Crustdata: {e.detail}")
    except Exception as e:
        logger.exception("Brief synthesis failed")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}")


@app.post("/playbook", response_model=PlaybookOutput)
async def playbook(req: DossierRequest) -> PlaybookOutput:
    try:
        async with asyncio.timeout(_TIMEOUT_SECONDS):
            raw = await build_playbook(req.company, req.role)
            return await synthesize_playbook(raw, req.role)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Dossier assembly timed out.")
    except DossierError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CrustdataError as e:
        logger.exception("Crustdata error")
        raise HTTPException(status_code=502, detail=f"Crustdata: {e.detail}")
    except Exception as e:
        logger.exception("Playbook synthesis failed")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}")
