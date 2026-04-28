from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os

app = FastAPI()

MANAGER_URL = os.getenv("MANAGER_URL", "http://trip-booking-manager:8000")

class TripRequest(BaseModel):
    destination: str
    travelerId: str

class ApprovalRequest(BaseModel):
    approved: bool

@app.post("/trips")
async def create_trip(req: TripRequest):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{MANAGER_URL}/trips", json=req.dict())
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/trips/{booking_id}")
async def get_trip(booking_id: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{MANAGER_URL}/trips/{booking_id}")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Trip not found")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/trips/{booking_id}/approve")
async def approve_trip(booking_id: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{MANAGER_URL}/trips/{booking_id}/approval", json={"approved": True})
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Trip not found")
            if resp.status_code == 400:
                raise HTTPException(status_code=400, detail=resp.json().get("detail"))
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/trips/{booking_id}/reject")
async def reject_trip(booking_id: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{MANAGER_URL}/trips/{booking_id}/approval", json={"approved": False})
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Trip not found")
            if resp.status_code == 400:
                raise HTTPException(status_code=400, detail=resp.json().get("detail"))
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))
