# Scripting Batch - Portal de Operaciones

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` and set your actual values:

```env
# Flask Configuration
SECRET_KEY=your-actual-secret-key-here

# Admin User Configuration (optional)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-admin-password

# SMB Server Configuration
SMB_SERVER=172.16.11.104
SMB_SHARE=pond
SMB_USERNAME=your-actual-username
SMB_PASSWORD=your-actual-password
SMB_BASE_PATH=incoming/Orexplore
```

**Important:** Never commit the `.env` file to version control. It's already in `.gitignore`.

**Admin User:** If you set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in the `.env` file, an admin user will be automatically created on first startup. The password is securely hashed and never stored in plain text.

### 3. Run the Application

```bash
python app.py
```

The application will run on `http://172.16.11.151:5001`

## Features

### Status Checker
- Compares batches entered in OP against data from the SMB server
- Highlights mismatches in red
- Provides edit functionality for batches

### Health Check Endpoint
Monitor application and SMB connectivity:

```bash
curl http://172.16.11.151:5001/health
```

Returns JSON with status of:
- Database connectivity
- SMB server connectivity
- Overall health status

### Logging
- Logs are written to `app.log`
- Console output for development
- Includes SMB connection attempts and errors

## Production Deployment

### Security Best Practices

1. **Set a strong SECRET_KEY**: Generate a random secret key
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Use environment variables**: Never hardcode credentials in code

3. **Disable debug mode**: Set `debug=False` in production

4. **Monitor logs**: Check `app.log` regularly for errors

5. **Health checks**: Use `/health` endpoint with monitoring tools

### Monitoring

The `/health` endpoint returns:
- `status`: "healthy" or "degraded"
- `services.database`: Status of local database files
- `services.smb`: Status of SMB server connectivity

Example response:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-09T15:45:00",
  "services": {
    "database": {
      "status": "ok",
      "batches_count": 42
    },
    "smb": {
      "status": "ok",
      "batches_found": 38
    }
  }
}
```

## Error Handling

The application now gracefully handles:
- SMB server unavailability
- Network timeouts
- Invalid credentials
- Missing files or directories

If the SMB server is unreachable, the Status Checker will still function but show no machine data.

## Troubleshooting

### SMB Connection Issues

Check logs in `app.log` for detailed error messages:

```bash
tail -f app.log
```

Common issues:
- Wrong credentials: Check `SMB_USERNAME` and `SMB_PASSWORD`
- Network issues: Verify `SMB_SERVER` is reachable
- Permission issues: Ensure user has read access to the share

### Application won't start

1. Verify all environment variables are set in `.env`
2. Check Python dependencies are installed
3. Ensure port 5001 is not in use

## Default Credentials

Default user (for first login):
- Username: `Felipe.Campos`
- Password: `WeScanRocks`

**Important:** Create new users after first login at `/create_user`
