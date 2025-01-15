# Misinformation Mitigation Project

## Overview

This project aims to develop a backend system for misinformation detection and mitigation. By leveraging language models and web search capabilities, we're creating a platform to combat the spread of false information online.

## Quick Start

### Prerequisites

- Docker
- Docker Compose

That's it! Docker will handle everything else, including creating a virtual environment, installing dependencies, and setting up the database.

### Setting up the development environment

1. Clone the repository:
   ```
   git clone https://github.com/ComplexData-MILA/veracity-eval-backend.git
   cd misinformation-mitigation
   ```

2. Create a `.env` file in the root directory and add the necessary environment variables:
   ```
    POSTGRES_USER=user
    POSTGRES_PASSWORD=password
    POSTGRES_DB=mitigation_misinformation_db
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
   ```

3. Build and start the Docker containers:
   ```
   docker-compose up --build
   ```

   This command will:
   - Create a virtual environment within the Docker container
   - Install all required dependencies
   - Set up the PostgreSQL database
   - Run database migrations
   - Start the application

4. The API will be available at `http://localhost:8001`. You can access the Swagger UI documentation at `http://localhost:8001/docs`.

### Running tests

To run the tests, use the following command:

```
docker-compose run app pytest
```

## Development Without Docker

If you prefer to develop without Docker, you'll need to:

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   Note, for proper dependencies, you will need python version 3.11

3. Set up a PostgreSQL database and update the `.env` file with its URL.

4. Run migrations:
   ```
   alembic upgrade head
   ```

5. Start the application:
   ```
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```

## Project Overview

 For more details on the project, please refer to the [Project Overview](https://github.com/ComplexData-MILA/veracity-eval-backend/wiki/Project-Overview) wiki page.

## API Specification

For detailed API documentation, please refer to the [API Specification](https://github.com/ComplexData-MILA/veracity-eval-backend/wiki/API-Specification) wiki page.

## Further Information

For more detailed information about the project, including its architecture, design decisions, and research paper, please refer to our [project wiki](https://github.com/ComplexData-MILA/veracity-eval-backend/wiki).