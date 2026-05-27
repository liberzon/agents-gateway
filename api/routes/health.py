import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from api.settings import api_settings
from db.session import get_db

######################################################
## Routes for the API Health
######################################################

health_router = APIRouter(tags=["Health"])


@health_router.get("/health")
def get_health(response: Response, db: Session = Depends(get_db)):
    """Check the health of the Api and database connection"""
    logging.info("Health check requested")

    # Check database connection
    try:
        # Execute a simple query to check if the database is connected
        db.execute(text("SELECT 1"))
        health_status = "success"
    except SQLAlchemyError as e:
        logging.error(f"Database connection error: {e}")
        health_status = "failure"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    result = {"status": health_status}
    logging.info(f"Health check response: {result}")
    return result


@health_router.get("/status")
def get_status():
    """Return the status of the API"""
    return {"status": "healthy", "service": "agents-gateway"}


@health_router.get("/")
def get_root():
    """Root endpoint that redirects to docs"""
    return {"message": "Welcome to Agents Gateway", "docs": "/docs", "version": api_settings.version}


@health_router.get("/version")
def get_version():
    """Return the version of the API"""
    return {"version": api_settings.version}
