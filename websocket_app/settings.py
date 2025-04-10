"""
Configuration settings for WebSocket handling
"""

# Throttling settings
STATUS_UPDATE_THROTTLE_SECONDS = 10

# WebSocket configuration
MAX_CONNECTIONS_PER_CLIENT = 2

# Logging settings
WEBSOCKET_DEBUG = True

# Status mappings between app and database
STATUS_MAPPINGS = {
    'ONLINE': 'DISPONIVEL',   # App status -> DB status
    'DISPONIVEL': 'DISPONIVEL',
    'OFFLINE': 'OFFLINE'
}
