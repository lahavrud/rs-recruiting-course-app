# RS Recruitment

![CI](https://github.com/lahavrud/rs-recruitment/actions/workflows/ci.yml/badge.svg)

**Vision:** A specialized CRM for a boutique recruitment agency.  
**Core Value:** Streamlining the flow from "Lead" (Job/Candidate) to "Match", with the Admin as the central gatekeeper.

---

## 🧭 Principles

- **Vertical Slices:** Develop features end-to-end (DB → Business Logic → API → Tests).  
- **Admin as Gatekeeper:** All public data (Companies, Jobs, Matches) require Admin approval.  
- **Hybrid Auth:** Admins & Companies are authenticated Users; Candidates are unauthenticated leads.  
- **Trunk-Based Development:** Docs/Chores → direct Main; Features → short-lived branches merged quickly.  
- **DevOps / Agile Deploy:**  
  - CI/CD ensures every push is tested and containerized.  
  - Dev Environment deploy **after first working slice**.  
  - Staging deploy **after multiple slices** for integration validation.  
  - Production deploy **after full MVP**.  
- **Low Friction MVP:** Minimal auth surface, minimal public access, focus on working vertical slices.

---

## Tech Stack

- **Python 3.12** - Core programming language
- **FastAPI** - Modern, fast web framework for building APIs
- **Pydantic** - Data validation using Python type annotations
- **Uvicorn** - ASGI server for running FastAPI applications
- **SQLModel** - Database ORM (SQLAlchemy + Pydantic)
- **Ruff** - Fast Python linter and code formatter
- **Docker** - Containerization for deployment

---

## Architecture

This project follows a **Modular Monolith** architecture with a **Vertical Slices** approach:

- **Vertical Slices**: Features are developed end-to-end (database → business logic → API), not by technical layers. Each feature is a complete vertical slice through the application stack.
- **Admin Gatekeeper**: Companies, Jobs, and Matches require Admin approval. Public input is never auto-trusted, ensuring data quality and security.

The system uses a hybrid authentication model where Admins and Companies are authenticated Users, while Candidates are unauthenticated leads (CandidateProfiles). This approach reduces complexity while maintaining flexibility for future enhancements.

---

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

- **[CONTEXT.md](docs/CONTEXT.md)** - Project context, coding standards, and domain model
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture, authentication model, and database schema
- **[ROADMAP.md](docs/ROADMAP.md)** - Product roadmap and development timeline
- **[API_DESIGN.md](docs/API_DESIGN.md)** - API design specifications

---

## Local Development

### Prerequisites

- Python 3.12+
- pip (Python package installer)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/lahavrud/rs-recruitment.git
   cd rs-recruitment
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables (optional, defaults are provided):
   ```bash
   # Set variables directly:
   export JWT_SECRET_KEY="your-secret-key-change-in-production"
   export DATABASE_URL="sqlite+aiosqlite:///./data/rs_recruitment.db"
   ```
   
   Or create a `.env` file in the project root with:
   ```bash
   JWT_SECRET_KEY=your-secret-key-change-in-production
   DATABASE_URL=sqlite+aiosqlite:///./data/rs_recruitment.db
   ```

   **AWS Configuration (Optional):**
   
   For production, configure AWS S3 and SES:
   ```bash
   # Storage Provider: 's3' or 'local' (default: 'local')
   STORAGE_PROVIDER=s3
   AWS_ACCESS_KEY_ID=your-access-key-id
   AWS_SECRET_ACCESS_KEY=your-secret-access-key
   AWS_REGION=us-east-1
   AWS_S3_BUCKET_NAME=your-bucket-name
   
   # Email Provider: 'ses' or 'smtp' (default: 'smtp')
   EMAIL_PROVIDER=ses
   AWS_SES_FROM_EMAIL=noreply@yourdomain.com
   ```
   
   For development/testing with SMTP:
   ```bash
   EMAIL_PROVIDER=smtp
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SMTP_FROM_EMAIL=your-email@gmail.com
   SMTP_USE_TLS=true
   ```
   
   See [AWS Setup](#aws-setup) section for detailed instructions.

5. Run database migrations:
   ```bash
   alembic upgrade head
   ```

6. (Optional) Seed an admin user:
   ```bash
   python scripts/seed_admin.py admin@example.com your-secure-password
   ```

### Running Locally (Without Docker)

After installation, run the development server:

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run the FastAPI application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: `http://localhost:8000`
- **Interactive API Docs (Swagger)**: `http://localhost:8000/docs`
- **Alternative API Docs (ReDoc)**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

### Running with Docker

#### Using Docker Compose (Recommended)

```bash
# Start the API
docker-compose up

# Or run in detached mode (background)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the API
docker-compose down
```

#### Using Docker directly

```bash
# Build the image
docker build -t rs-recruitment .

# Run the container
docker run -p 8000:8000 rs-recruitment

# Or with environment variables
docker run -p 8000:8000 \
  -e JWT_SECRET_KEY="your-production-secret-key" \
  rs-recruitment
```

The API will be available at `http://localhost:8000`.

**Environment Variables:**
- `JWT_SECRET_KEY` - Secret key for JWT token signing (default: "your-secret-key-change-in-production")
- `JWT_ALGORITHM` - JWT algorithm (default: "HS256")
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration in minutes (default: 30)
- `DATABASE_URL` - Database connection string (default: `sqlite+aiosqlite:///./data/rs_recruitment.db` for both local and Docker)

**AWS & Storage Configuration:**
- `STORAGE_PROVIDER` - Storage provider: `s3` or `local` (default: `local`)
- `AWS_ACCESS_KEY_ID` - AWS access key ID (required for S3)
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key (required for S3)
- `AWS_REGION` - AWS region (default: `us-east-1`)
- `AWS_S3_BUCKET_NAME` - S3 bucket name (required when using S3)
- `LOCAL_STORAGE_PATH` - Local storage directory (default: `./storage`)

**Email Configuration:**
- `EMAIL_PROVIDER` - Email provider: `ses` or `smtp` (default: `smtp`)
- `AWS_SES_FROM_EMAIL` - SES sender email (required when using SES, must be verified)
- `SMTP_HOST` - SMTP server hostname (default: `localhost`)
- `SMTP_PORT` - SMTP server port (default: `587`)
- `SMTP_USER` - SMTP username (optional)
- `SMTP_PASSWORD` - SMTP password (optional)
- `SMTP_FROM_EMAIL` - SMTP sender email (optional)
- `SMTP_USE_TLS` - Use TLS encryption (default: `true`)

---

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py
```

---

## Database Migrations

Manage database schema changes with Alembic:

```bash
# Create a new migration
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history
```

---

## API Endpoints

Current available endpoints:

**Authentication:**
- `POST /auth/register` - Register a new company user
- `POST /auth/login` - Login and receive JWT token

**System:**
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

---

## Code Quality

Run the linter to check code quality:
```bash
ruff check .
```

For automated formatting:
```bash
ruff format .
```

---

## AWS Setup

### AWS S3 Setup (File Storage)

1. **Create an S3 Bucket:**
   - Log in to AWS Console
   - Navigate to S3 service
   - Create a new bucket (choose a unique name)
   - Configure bucket permissions and CORS if needed for frontend uploads

2. **Create IAM User with S3 Permissions:**
   - Navigate to IAM service
   - Create a new user (e.g., `rs-recruitment-s3`)
   - Attach policy: `AmazonS3FullAccess` (or create custom policy with least privilege)
   - Create access keys and save them securely

3. **Configure Environment Variables:**
   ```bash
   STORAGE_PROVIDER=s3
   AWS_ACCESS_KEY_ID=your-access-key-id
   AWS_SECRET_ACCESS_KEY=your-secret-access-key
   AWS_REGION=us-east-1
   AWS_S3_BUCKET_NAME=your-bucket-name
   ```

### AWS SES Setup (Email Service)

1. **Verify Email Address/Domain:**
   - Log in to AWS Console
   - Navigate to SES service
   - Verify the email address or domain you want to send from
   - If in SES sandbox, verify recipient emails too

2. **Request Production Access (if needed):**
   - By default, SES is in sandbox mode (can only send to verified emails)
   - Request production access to send to any email address

3. **Create IAM User with SES Permissions:**
   - Navigate to IAM service
   - Create a new user (e.g., `rs-recruitment-ses`)
   - Attach policy: `AmazonSESFullAccess` (or create custom policy)
   - Create access keys and save them securely

4. **Configure Environment Variables:**
   ```bash
   EMAIL_PROVIDER=ses
   AWS_SES_FROM_EMAIL=noreply@yourdomain.com
   AWS_ACCESS_KEY_ID=your-access-key-id  # Can reuse S3 keys if same user
   AWS_SECRET_ACCESS_KEY=your-secret-access-key
   AWS_REGION=us-east-1
   ```

### Security Best Practices

- **Never commit AWS credentials to the repository**
- Use environment variables or AWS IAM roles (when deploying to EC2/ECS/Lambda)
- Use least-privilege IAM policies (only grant necessary permissions)
- Rotate access keys regularly
- Use separate IAM users for different services if needed

### Development/Testing

For local development, you can use:
- **Storage:** `STORAGE_PROVIDER=local` (files stored in `./storage` directory)
- **Email:** `EMAIL_PROVIDER=smtp` with Gmail or other SMTP provider

---

## Seeding Admin User

To create an admin user for testing:

```bash
python scripts/seed_admin.py <email> <password>
```

Example:
```bash
python scripts/seed_admin.py admin@example.com securepassword123
```

## Testing AWS Integration

To manually test your AWS S3 and SES configuration with real credentials:

```bash
python scripts/test_aws_integration.py
```

This script will:
- Test file upload/download/delete with your configured storage provider (S3 or Local)
- Optionally send a test email to verify email configuration (SES or SMTP)
- Show detailed results for each operation

**Note:** Make sure your `.env` file is configured with your AWS credentials before running this script.
