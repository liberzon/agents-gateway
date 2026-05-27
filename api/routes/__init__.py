"""
API Routes Package

This package contains all the API routes for the application.

Versioned routes:
- v2: Version 2 API routes (current production API)

Non-versioned routes:
- health.py: Health check endpoint (available at both root and versioned paths)
- admin.py: Administrative endpoints for cache management and monitoring
"""

# Import routers for easier access
from api.routes.health import health_router
from api.routes.v2_router import get_v2_router
