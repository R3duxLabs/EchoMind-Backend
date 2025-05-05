# EchoMind Frontend Integration

This directory contains static files and resources for frontend integration with the EchoMind API.

## Directory Structure

- `/css` - CSS stylesheets
- `/js` - JavaScript files including the EchoMind client library
- `/img` - Images and icons

## EchoMind Client Library

The `echomind-client.js` file provides a complete client library for interacting with the EchoMind API. The library includes:

- Authentication (login/logout)
- WebSocket integration for real-time updates
- Memory management (create, read, update, delete)
- UI state synchronization
- Batch operations
- Data visualization
- Pickaxe knowledge base integration

### Usage Example

```javascript
// Create a new client instance
const client = new EchoMindClient({
  apiBaseUrl: '/api',
  useWebsocket: true
});

// Authenticate
await client.authenticate({
  email: 'user@example.com',
  password: 'password'
});

// Get frontend configuration
const config = await client.getConfig();

// Set up real-time notification handling
client.on('notification', (notification) => {
  console.log(`Notification: ${notification.title} - ${notification.message}`);
  
  // Show notification in UI
  // ...
});

// Get memory data
const memories = await client.getOptimizedMemory({
  limit: 50,
  memoryTypes: ['general', 'episodic']
});

// Create a new memory
await client.createMemory({
  memory_type: 'general',
  content: 'This is a new memory',
  tags: ['important', 'work']
});

// Get memory visualization
const visualization = await client.getMemoryVisualization('graph', {
  maxNodes: 50,
  includeTags: true
});
```

## WebSocket Integration

The WebSocket integration allows for real-time updates from the server. The connection is established automatically when authenticating with the API.

### WebSocket Events

The following events are available:

- `connection_established` - WebSocket connection established
- `connection_closed` - WebSocket connection closed
- `connection_error` - WebSocket connection error
- `memory_update` - Memory created, updated, or deleted
- `notification` - Notification for the user
- `streaming` - Streaming response chunks
- `error` - Error message

### WebSocket Usage Example

```javascript
// Set up event handlers
client.on('memory_update', (update) => {
  console.log(`Memory update: ${update.operation} - ${update.memory_id}`);
  
  // Update UI based on the operation
  if (update.operation === 'created') {
    // Add new memory to UI
    // ...
  } else if (update.operation === 'updated') {
    // Update existing memory in UI
    // ...
  } else if (update.operation === 'deleted') {
    // Remove memory from UI
    // ...
  }
});

client.on('notification', (notification) => {
  // Show notification in UI
  // ...
});

// Test notification
await client.sendTestNotification({
  title: 'Hello',
  message: 'This is a test notification',
  level: 'info'
});
```

## Batch Operations

Batch operations allow multiple API calls to be made in a single request, reducing round-trips and improving performance.

### Batch Operations Example

```javascript
const results = await client.batchOperations([
  {
    type: 'get_memory',
    data: { id: 'mem-123' }
  },
  {
    type: 'create_memory',
    data: {
      memory_type: 'general',
      content: 'This is a new memory'
    }
  },
  {
    type: 'update_state',
    data: {
      state_id: 'state-123',
      state_data: { sidebar_collapsed: true }
    }
  }
]);

// Process results
for (const result of results.results) {
  console.log(`Operation ${result.type} completed`);
  // Process result based on operation type
  // ...
}

// Check for errors
if (results.error_count > 0) {
  console.error(`${results.error_count} operations failed`);
  for (const error of results.errors) {
    console.error(`Error in operation ${error.operation.type}: ${error.error}`);
  }
}
```

## Frontend Routes

The EchoMind API provides several routes specifically designed for frontend applications:

- `/frontend/config` - Get frontend configuration
- `/frontend/ui-state` - Synchronize UI state
- `/frontend/preferences` - Get or update user preferences
- `/frontend/batch` - Perform batch operations
- `/frontend/optimized-memory` - Get memory data optimized for frontend rendering
- `/frontend/dashboard-data` - Get aggregate data for dashboard display
- `/frontend/test-notification` - Send a test notification via WebSocket

These routes are designed to provide data in formats that are optimized for frontend consumption, reducing the need for data transformation in the client.