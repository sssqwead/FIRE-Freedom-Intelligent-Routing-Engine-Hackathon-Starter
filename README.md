# FIRE (Freedom Intelligent Routing Engine)

## Overview

FIRE is an intelligent ticket routing engine designed to automatically
process, enrich, and distribute incoming tickets across business units
and managers.

This project was built as a hackathon-ready MVP and demonstrates
full-stack integration including backend APIs, AI-based processing,
geolocation routing, and a Streamlit dashboard interface.

------------------------------------------------------------------------

## Tech Stack

### Backend

-   FastAPI
-   SQLAlchemy
-   PostgreSQL

### Frontend / UI

-   Streamlit

### Additional Integrations

-   OpenStreetMap (Geolocation)
-   Optional LLM integration (disabled by default)

------------------------------------------------------------------------

## Core Features

-   Upload tickets, managers, and business units via CSV
-   AI-powered enrichment (rule-based by default)
-   Optional LLM-based enhancement
-   Geolocation-based routing
-   Round-robin distribution logic for top 2 business units
-   Dashboard with aggregated statistics
-   REST API documentation available via Swagger

------------------------------------------------------------------------

## Architecture Flow

CSV Input → Processing → AI Enrichment → Routing Logic → Database
Storage → UI Visualization

------------------------------------------------------------------------

## Running the Project

### Option 1: Docker (Recommended)

docker compose up --build

UI: http://localhost:8501\
API Docs: http://localhost:8000/docs

### Option 2: Manual Setup

1.  Start PostgreSQL
2.  Install dependencies
3.  Run backend (FastAPI)
4.  Run Streamlit UI

------------------------------------------------------------------------

## Future Improvements

-   Full LLM automation
-   SaaS-ready deployment
-   Role-based authentication
-   Cloud deployment (AWS/GCP/Azure)
-   Advanced analytics dashboard

------------------------------------------------------------------------

## License

Hackathon MVP -- Extend and modify as needed.
