# Auction API

A Django REST Framework based API for an online auction system.

## Features

- User registration and JWT authentication
- Create and manage auctions
- Place bids on active auctions
- Automatic auction status updates
- Admin dashboard for system management
- API documentation with Swagger/OpenAPI

## Technical Stack

- Django 4.x
- Django REST Framework
- PostgreSQL
- JWT Authentication with Simple JWT
- OpenAPI/Swagger documentation

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- PostgreSQL
- pip (Python package manager)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/auction-api.git
cd auction-api
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure PostgreSQL:

Create a database for the project:

```sql
CREATE DATABASE auction_db;
CREATE USER auction_user WITH PASSWORD 'your_password';
ALTER ROLE auction_user SET client_encoding TO 'utf8';
ALTER ROLE auction_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE auction_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE auction_db TO auction_user;
```

5. Update Django settings:

Create a `.env` file in the project root with:

```
DEBUG=True
SECRET_KEY=your_secret_key
DATABASE_URL=postgres://auction_user:your_password@localhost:5432/auction_db
```

6. Run migrations:

```bash
python manage.py migrate
```

7. Create a superuser:

```bash
python manage.py createsuperuser
```

8. Run the development server:

```bash
python manage.py runserver
```

## API Endpoints

### Authentication

- `POST /auth/register/` - Register a new user
- `POST /auth/login/` - Login and get JWT tokens
- `POST /auth/refresh/` - Refresh JWT token
- `GET /auth/profile/` - Get current user profile

### Auctions

- `GET /auctions/` - List all auctions
- `POST /auctions/` - Create a new auction
- `GET /auctions/{id}/` - Get auction details
- `PUT /auctions/{id}/` - Update auction (owner only)
- `DELETE /auctions/{id}/` - Delete auction (owner or admin only)
- `GET /auctions/{id}/bids/` - Get bids for an auction
- `POST /auctions/{id}/place_bid/` - Place a bid on an auction

### Bids

- `GET /bids/` - List all bids (for current user)
- `GET /bids/{id}/` - Get bid details

### Documentation

- `GET /swagger/` - Swagger UI
- `GET /redoc/` - ReDoc UI

## Testing

Run the test suite:

```bash
pytest
```

## API Documentation

When the server is running, visit:

- Swagger UI: [http://localhost:8000/swagger/](http://localhost:8000/swagger/)
- ReDoc: [http://localhost:8000/redoc/](http://localhost:8000/redoc/)

## Authentication

The API uses JWT (JSON Web Tokens) for authentication. To authenticate:

1. Register a new user or log in with existing credentials.
2. Include the token in all requests by adding the following header:
   ```
   Authorization: Bearer <your_token>
   ```

## Filtering Auctions

The auctions endpoint supports filtering:

- `?status=active` - Filter by status (pending, active, closed)
- `?creator=1` - Filter by creator ID
- `?my=true` - Show only auctions created by the current user
- `?won=true` - Show only auctions won by the current user
- `?search=keyword` - Search auctions by title or description

## License

This project is licensed under the MIT License - see the LICENSE file for details.