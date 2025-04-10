import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

class WebSocketConnectionManager:
    """
    Manager class to track and limit WebSocket connections
    """
    def __init__(self):
        self.active_connections = {}
        self.connection_counts = defaultdict(int)
        self.last_status_update = defaultdict(float)
        self.STATUS_UPDATE_THROTTLE = 10  # seconds between status updates

    def register_connection(self, client_id, channel_name):
        """Register a new connection for a client"""
        if client_id in self.active_connections:
            # Client already has a connection, close old one before registering new
            logger.warning(f"Client {client_id} already has an active connection. Replacing.")
        
        self.active_connections[client_id] = channel_name
        self.connection_counts[client_id] += 1
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")

    def unregister_connection(self, client_id):
        """Unregister a client connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected. Remaining connections: {len(self.active_connections)}")
    
    def can_update_status(self, client_id):
        """Check if client can update status (throttling)"""
        now = time.time()
        last_update = self.last_status_update.get(client_id, 0)
        
        if now - last_update < self.STATUS_UPDATE_THROTTLE:
            logger.warning(f"Status update throttled for client {client_id}. Last update: {last_update}, now: {now}, diff: {now - last_update}")
            return False
        
        logger.debug(f"Status update permitted for client {client_id}")
        self.last_status_update[client_id] = now
        return True
    
    def get_connection_count(self):
        """Return the total number of active connections"""
        return len(self.active_connections)
    
    def get_client_connections(self):
        """Return connection statistics"""
        return {
            'total': len(self.active_connections),
            'per_client': dict(self.connection_counts)
        }

# Singleton instance
connection_manager = WebSocketConnectionManager()
