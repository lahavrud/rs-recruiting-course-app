# RS Recruitment

**RS Recruitment** is a specialized CRM for a boutique recruitment agency. The system streamlines the flow from "Lead" (Job/Candidate) to "Match", with the Admin as the central gatekeeper. This modular monolith is built with a focus on clean, maintainable MVP delivery.


## Tech Stack

- **Python 3.12** - Core programming language
- **FastAPI** - Modern, fast web framework for building APIs
- **Pydantic** - Data validation using Python type annotations
- **Uvicorn** - ASGI server for running FastAPI applications
- **SQLModel** - Database ORM (SQLAlchemy + Pydantic)
- **Ruff** - Fast Python linter and code formatter
- **Docker** - Containerization for deployment

## Architecture

This project follows a **Modular Monolith** architecture with a **Vertical Slices** approach:

- **Vertical Slices**: Features are developed end-to-end (database → business logic → API), not by technical layers. Each feature is a complete vertical slice through the application stack.
- **Admin Gatekeeper**: Companies, Jobs, and Matches require Admin approval. Public input is never auto-trusted, ensuring data quality and security.

The system uses a hybrid authentication model where Admins and Companies are authenticated Users, while Candidates are unauthenticated leads (CandidateProfiles). This approach reduces complexity while maintaining flexibility for future enhancements.

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

- **[CONTEXT.md](docs/CONTEXT.md)** - Project context, coding standards, and domain model
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture, authentication model, and database schema
- **[ROADMAP.md](docs/ROADMAP.md)** - Product roadmap and development timeline
- **[API_DESIGN.md](docs/API_DESIGN.md)** - API design specifications

## Local Development

### Prerequisites

- Python 3.12+
- pip (Python package installer)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd rs-recruitment
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

### Running with Docker

```bash
# Build the image
docker build -t rs-recruitment .

# Run the container
docker run -p 8000:8000 rs-recruitment
```

The API will be available at `http://localhost:8000`.

### Code Quality

Run the linter to check code quality:
```bash
ruff check .
```

For automated formatting, you can also use:
```bash
ruff format .
```
