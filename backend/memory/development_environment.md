---
name: backend dev environment
description: Backend development environment configuration and startup instructions
type: reference
---

## Backend Service Startup

**Working Directory**: `/home/tim/workspace/cmdb/backend`

**Virtual Environment**: `backend/venv`

### Startup Command
```bash
cd /home/tim/workspace/cmdb/backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**--reload**: 自动重载代码更改，开发模式必备

### Background Startup (Development)
```bash
cd /home/tim/workspace/cmdb/backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/uvicorn.log 2>&1 &
```

### Database Connection
- PostgreSQL: `127.0.0.1:5432`
- Database: `cmdb`
- User: `navi`
- Password: `uy7YGp4bqwljX5N`

### Redis Connection
- Address: `127.0.0.1:6379`
- Password: `EgYGGE6GqDgAJU8dSWkY`
