from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

VALID_API_KEYS = {
    "ECHO_API_KEY": "echomind-echo-key",
    "ELORA_API_KEY": "echomind-elora-key",
    "ELLIOT_API_KEY": "echomind-elliot-key",
    "PARENTING_API_KEY": "echomind-parenting-key",
    "BRIDGE_API_KEY": "echomind-bridge-key",
    "ADMIN_API_KEY": "echomind-admin-key",
    "WHISPERER_API_KEY": "echomind-whisperer-key",
    "MIRROR_API_KEY": "echomind-mirror-key",
    "PULSE_API_KEY": "echomind-pulse-key"
}

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key not in VALID_API_KEYS.values():
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
