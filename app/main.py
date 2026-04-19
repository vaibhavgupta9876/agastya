import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.models.schemas import (
    BriefOutput,
    CompanyMatch,
    DossierRequest,
    IdentifyRequest,
    IdentifyResponse,
    PlaybookOutput,
)
from app.services.cache import cache
from app.services.crustdata import CrustdataError, identify_company
from app.services.dossier import DossierError, build_brief, build_playbook
from app.services.prewarm import registry as prewarm_registry
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


@app.post("/identify", response_model=IdentifyResponse)
async def identify(req: IdentifyRequest) -> IdentifyResponse:
    """Typeahead-friendly company disambiguation. Returns a compact match list."""
    try:
        raw = await identify_company(req.query)
    except CrustdataError as e:
        logger.exception("Crustdata identify failed")
        raise HTTPException(status_code=502, detail=f"Crustdata: {e.detail}")

    if not raw or not raw[0].get("matches"):
        return IdentifyResponse(matches=[])

    out: list[CompanyMatch] = []
    for m in raw[0].get("matches", [])[:6]:
        basic = ((m.get("company_data") or {}).get("basic_info") or {})
        industries = basic.get("industries") or []
        out.append(
            CompanyMatch(
                name=basic.get("name") or "",
                domain=basic.get("primary_domain"),
                logo_url=basic.get("logo_permalink"),
                industry=industries[0] if industries else None,
                employee_count_range=basic.get("employee_count_range"),
                linkedin_url=basic.get("professional_network_url"),
            )
        )
    return IdentifyResponse(matches=[m for m in out if m.name])


class PrewarmRequest(BaseModel):
    company: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)


@app.post("/prewarm", status_code=202)
async def prewarm(req: PrewarmRequest) -> dict[str, str]:
    """
    Fire-and-forget: kick off the role-independent Crustdata fan-out for a
    picked company so the eventual /brief or /playbook hits a warm cache.
    """
    prewarm_registry.prewarm_in_background(req.company, req.domain)
    return {"status": "accepted"}


@app.post("/brief", response_model=BriefOutput)
async def brief(req: DossierRequest) -> BriefOutput:
    key = cache.key("brief", req.company, req.role, req.domain)
    cached = cache.get(key)
    if cached is not None:
        return BriefOutput.model_validate(cached)
    try:
        async with asyncio.timeout(_TIMEOUT_SECONDS):
            raw = await build_brief(req.company, req.role, domain=req.domain)
            result = await synthesize_brief(raw, req.role)
            cache.set(key, result.model_dump())
            return result
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
    key = cache.key("playbook", req.company, req.role, req.domain)
    cached = cache.get(key)
    if cached is not None:
        return PlaybookOutput.model_validate(cached)
    try:
        async with asyncio.timeout(_TIMEOUT_SECONDS):
            raw = await build_playbook(req.company, req.role, domain=req.domain)
            result = await synthesize_playbook(raw, req.role)
            cache.set(key, result.model_dump())
            return result
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
