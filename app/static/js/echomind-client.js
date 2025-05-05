/**
 * EchoMind API Client
 * 
 * A JavaScript client library for interacting with the EchoMind API.
 * This library provides methods for:
 * - Authentication
 * - Memory management
 * - WebSocket communication
 * - UI state synchronization
 * - Batch operations
 */

class EchoMindClient {
  /**
   * Create a new EchoMind client instance
   * 
   * @param {Object} options Configuration options
   * @param {string} options.apiBaseUrl Base URL for the API (default: '/api')
   * @param {string} options.apiKey API key for authentication
   * @param {string} options.userId User ID (if already authenticated)
   * @param {boolean} options.useWebsocket Whether to use WebSocket for real-time updates (default: true)
   * @param {boolean} options.autoConnect Whether to automatically connect to WebSocket (default: true)
   */
  constructor(options = {}) {
    this.apiBaseUrl = options.apiBaseUrl || '/api';
    this.apiKey = options.apiKey || null;
    this.userId = options.userId || null;
    this.useWebsocket = options.useWebsocket !== false;
    this.autoConnect = options.autoConnect !== false;
    
    // WebSocket connection
    this.websocket = null;
    this.websocketConnected = false;
    this.websocketReconnectAttempts = 0;
    this.websocketMaxReconnectAttempts = 5;
    this.websocketReconnectDelay = 1000; // 1 second initial delay, will increase exponentially
    
    // Event handlers
    this.eventHandlers = {
      'connection_established': [],
      'connection_closed': [],
      'connection_error': [],
      'memory_update': [],
      'notification': [],
      'streaming': [],
      'error': []
    };
    
    // Request queue for offline mode (future implementation)
    this.requestQueue = [];
    
    // Initialize the client
    this._init();
  }
  
  /**
   * Initialize the client
   * 
   * @private
   */
  _init() {
    // Add event listeners for connection state
    window.addEventListener('online', () => this._handleOnline());
    window.addEventListener('offline', () => this._handleOffline());
    
    // Connect to WebSocket if autoConnect is true
    if (this.useWebsocket && this.autoConnect && this.userId) {
      this.connectWebsocket();
    }
  }
  
  /**
   * Handle online event
   * 
   * @private
   */
  _handleOnline() {
    console.log('EchoMind client: Device is online');
    
    // Reconnect WebSocket if needed
    if (this.useWebsocket && !this.websocketConnected && this.userId) {
      this.connectWebsocket();
    }
    
    // Process request queue (future implementation)
  }
  
  /**
   * Handle offline event
   * 
   * @private
   */
  _handleOffline() {
    console.log('EchoMind client: Device is offline');
    
    // Close WebSocket connection
    if (this.websocket) {
      this.websocket.close();
      this.websocketConnected = false;
    }
  }
  
  /**
   * Make an API request
   * 
   * @param {string} method HTTP method
   * @param {string} endpoint API endpoint
   * @param {Object} data Request data
   * @returns {Promise<Object>} API response
   */
  async request(method, endpoint, data = null) {
    const url = `${this.apiBaseUrl}${endpoint}`;
    
    const headers = {
      'Content-Type': 'application/json'
    };
    
    // Add API key if available
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }
    
    const options = {
      method,
      headers,
      credentials: 'include'
    };
    
    // Add request body for POST, PUT, PATCH
    if (['POST', 'PUT', 'PATCH'].includes(method.toUpperCase()) && data) {
      options.body = JSON.stringify(data);
    }
    
    try {
      const response = await fetch(url, options);
      
      // Handle non-OK responses
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.message || `API error: ${response.status}`);
      }
      
      // Return JSON response
      return await response.json();
    } catch (error) {
      console.error(`EchoMind client error: ${error.message}`);
      throw error;
    }
  }
  
  /**
   * Connect to the WebSocket server
   * 
   * @returns {Promise<void>}
   */
  connectWebsocket() {
    if (!this.userId) {
      throw new Error('User ID is required for WebSocket connection');
    }
    
    if (this.websocket) {
      this.websocket.close();
    }
    
    return new Promise((resolve, reject) => {
      try {
        // Create WebSocket URL with query parameters
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}${this.apiBaseUrl}/ws/${this.userId}?client=web&version=1.0`;
        
        // Create WebSocket connection
        this.websocket = new WebSocket(wsUrl);
        
        // Set up event handlers
        this.websocket.onopen = () => {
          console.log('EchoMind client: WebSocket connected');
          this.websocketConnected = true;
          this.websocketReconnectAttempts = 0;
          
          // Set up heartbeat
          this._startHeartbeat();
          
          // Notify event listeners
          this._triggerEvent('connection_established', {
            timestamp: new Date().toISOString()
          });
          
          resolve();
        };
        
        this.websocket.onclose = (event) => {
          console.log(`EchoMind client: WebSocket closed (code: ${event.code})`);
          this.websocketConnected = false;
          
          // Notify event listeners
          this._triggerEvent('connection_closed', {
            code: event.code,
            reason: event.reason,
            timestamp: new Date().toISOString()
          });
          
          // Attempt to reconnect
          this._attemptReconnect();
        };
        
        this.websocket.onerror = (error) => {
          console.error('EchoMind client: WebSocket error', error);
          
          // Notify event listeners
          this._triggerEvent('connection_error', {
            error: error.message || 'Unknown error',
            timestamp: new Date().toISOString()
          });
          
          reject(error);
        };
        
        this.websocket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this._handleWebsocketMessage(message);
          } catch (error) {
            console.error('EchoMind client: Error parsing WebSocket message', error);
          }
        };
        
      } catch (error) {
        console.error('EchoMind client: Error connecting to WebSocket', error);
        reject(error);
      }
    });
  }
  
  /**
   * Start WebSocket heartbeat
   * 
   * @private
   */
  _startHeartbeat() {
    // Clear any existing heartbeat
    if (this._heartbeatInterval) {
      clearInterval(this._heartbeatInterval);
    }
    
    // Send heartbeat every 30 seconds
    this._heartbeatInterval = setInterval(() => {
      if (this.websocketConnected) {
        this.sendWebsocketMessage({
          type: 'heartbeat',
          client_timestamp: new Date().toISOString()
        });
      }
    }, 30000);
  }
  
  /**
   * Attempt to reconnect to WebSocket
   * 
   * @private
   */
  _attemptReconnect() {
    if (this.websocketReconnectAttempts >= this.websocketMaxReconnectAttempts) {
      console.log('EchoMind client: Maximum reconnect attempts reached');
      return;
    }
    
    // Calculate delay with exponential backoff
    const delay = this.websocketReconnectDelay * Math.pow(2, this.websocketReconnectAttempts);
    this.websocketReconnectAttempts++;
    
    console.log(`EchoMind client: Reconnecting in ${delay}ms (attempt ${this.websocketReconnectAttempts})`);
    
    setTimeout(() => {
      if (!this.websocketConnected) {
        this.connectWebsocket().catch(() => {
          // Error handled in connectWebsocket
        });
      }
    }, delay);
  }
  
  /**
   * Handle WebSocket message
   * 
   * @param {Object} message The WebSocket message
   * @private
   */
  _handleWebsocketMessage(message) {
    const messageType = message.type || 'unknown';
    
    // Handle special message types
    switch (messageType) {
      case 'heartbeat':
        // Heartbeat response, no need to handle
        break;
        
      case 'connection_established':
        // Connection established message
        console.log('EchoMind client: Connection established', message);
        break;
        
      default:
        // Trigger event for the message type
        this._triggerEvent(messageType, message);
        break;
    }
  }
  
  /**
   * Send a message via WebSocket
   * 
   * @param {Object} message The message to send
   * @returns {boolean} Whether the message was sent
   */
  sendWebsocketMessage(message) {
    if (!this.websocketConnected) {
      console.error('EchoMind client: Cannot send message, WebSocket not connected');
      return false;
    }
    
    try {
      this.websocket.send(JSON.stringify(message));
      return true;
    } catch (error) {
      console.error('EchoMind client: Error sending WebSocket message', error);
      return false;
    }
  }
  
  /**
   * Add an event listener
   * 
   * @param {string} eventType Event type
   * @param {Function} callback Callback function
   */
  on(eventType, callback) {
    if (!this.eventHandlers[eventType]) {
      this.eventHandlers[eventType] = [];
    }
    
    this.eventHandlers[eventType].push(callback);
  }
  
  /**
   * Remove an event listener
   * 
   * @param {string} eventType Event type
   * @param {Function} callback Callback function
   */
  off(eventType, callback) {
    if (!this.eventHandlers[eventType]) {
      return;
    }
    
    this.eventHandlers[eventType] = this.eventHandlers[eventType].filter(
      (cb) => cb !== callback
    );
  }
  
  /**
   * Trigger an event
   * 
   * @param {string} eventType Event type
   * @param {Object} data Event data
   * @private
   */
  _triggerEvent(eventType, data) {
    if (!this.eventHandlers[eventType]) {
      return;
    }
    
    for (const callback of this.eventHandlers[eventType]) {
      try {
        callback(data);
      } catch (error) {
        console.error(`EchoMind client: Error in event handler for ${eventType}`, error);
      }
    }
  }
  
  /**
   * Authenticate with the API
   * 
   * @param {Object} credentials Authentication credentials
   * @param {string} credentials.email User email
   * @param {string} credentials.password User password
   * @returns {Promise<Object>} Authentication result
   */
  async authenticate(credentials) {
    const response = await this.request('POST', '/auth/login', credentials);
    
    if (response.status === 'ok' && response.data) {
      // Store authentication data
      this.apiKey = response.data.api_key;
      this.userId = response.data.user_id;
      
      // Connect to WebSocket if enabled
      if (this.useWebsocket && !this.websocketConnected) {
        this.connectWebsocket().catch(console.error);
      }
    }
    
    return response;
  }
  
  /**
   * Logout from the API
   * 
   * @returns {Promise<Object>} Logout result
   */
  async logout() {
    // Close WebSocket connection
    if (this.websocket) {
      this.websocket.close();
      this.websocketConnected = false;
    }
    
    // Clear authentication data
    const wasAuthenticated = !!this.apiKey;
    this.apiKey = null;
    this.userId = null;
    
    // Call logout endpoint if was authenticated
    if (wasAuthenticated) {
      return await this.request('POST', '/auth/logout');
    }
    
    return { status: 'ok' };
  }
  
  /**
   * Get frontend configuration
   * 
   * @returns {Promise<Object>} Frontend configuration
   */
  async getConfig() {
    return await this.request('GET', '/frontend/config');
  }
  
  /**
   * Synchronize UI state
   * 
   * @param {Object} stateData UI state data
   * @param {string} stateId Optional state ID
   * @returns {Promise<Object>} Synchronized state
   */
  async syncUIState(stateData, stateId = null) {
    if (!this.userId) {
      throw new Error('User ID is required for UI state synchronization');
    }
    
    let endpoint = `/frontend/ui-state?user_id=${this.userId}`;
    if (stateId) {
      endpoint += `&state_id=${stateId}`;
    }
    
    return await this.request('POST', endpoint, stateData);
  }
  
  /**
   * Get UI state
   * 
   * @param {string} stateId State ID
   * @returns {Promise<Object>} UI state
   */
  async getUIState(stateId) {
    return await this.request('GET', `/frontend/ui-state/${stateId}`);
  }
  
  /**
   * Get user preferences
   * 
   * @returns {Promise<Object>} User preferences
   */
  async getPreferences() {
    if (!this.userId) {
      throw new Error('User ID is required to get preferences');
    }
    
    return await this.request('GET', `/frontend/preferences/${this.userId}`);
  }
  
  /**
   * Update user preferences
   * 
   * @param {Object} preferences Preference data
   * @returns {Promise<Object>} Updated preferences
   */
  async updatePreferences(preferences) {
    if (!this.userId) {
      throw new Error('User ID is required to update preferences');
    }
    
    return await this.request('POST', `/frontend/preferences?user_id=${this.userId}`, preferences);
  }
  
  /**
   * Perform batch operations
   * 
   * @param {Array<Object>} operations Operations to perform
   * @returns {Promise<Object>} Batch operation results
   */
  async batchOperations(operations) {
    return await this.request('POST', '/frontend/batch', { operations });
  }
  
  /**
   * Get optimized memory data
   * 
   * @param {Object} options Query options
   * @param {number} options.limit Maximum number of items to return
   * @param {string} options.since Only return items since this timestamp
   * @param {Array<string>} options.memoryTypes Memory types to include
   * @param {boolean} options.includeMetadata Whether to include metadata
   * @returns {Promise<Object>} Memory data
   */
  async getOptimizedMemory(options = {}) {
    if (!this.userId) {
      throw new Error('User ID is required to get memory data');
    }
    
    let endpoint = `/frontend/optimized-memory/${this.userId}`;
    
    // Add query parameters
    const params = new URLSearchParams();
    
    if (options.limit) {
      params.append('limit', options.limit);
    }
    
    if (options.since) {
      params.append('since', options.since);
    }
    
    if (options.memoryTypes) {
      for (const type of options.memoryTypes) {
        params.append('memory_types', type);
      }
    }
    
    if (options.includeMetadata !== undefined) {
      params.append('include_metadata', options.includeMetadata);
    }
    
    // Add query string to endpoint
    const queryString = params.toString();
    if (queryString) {
      endpoint += `?${queryString}`;
    }
    
    return await this.request('GET', endpoint);
  }
  
  /**
   * Get dashboard data
   * 
   * @returns {Promise<Object>} Dashboard data
   */
  async getDashboardData() {
    if (!this.userId) {
      throw new Error('User ID is required to get dashboard data');
    }
    
    return await this.request('GET', `/frontend/dashboard-data/${this.userId}`);
  }
  
  /**
   * Send a test notification
   * 
   * @param {Object} options Notification options
   * @param {string} options.title Notification title
   * @param {string} options.message Notification message
   * @param {string} options.level Notification level (info, success, warning, error)
   * @returns {Promise<Object>} Result
   */
  async sendTestNotification(options = {}) {
    if (!this.userId) {
      throw new Error('User ID is required to send a notification');
    }
    
    let endpoint = `/frontend/test-notification/${this.userId}`;
    
    // Add query parameters
    const params = new URLSearchParams();
    
    if (options.title) {
      params.append('title', options.title);
    }
    
    if (options.message) {
      params.append('message', options.message);
    }
    
    if (options.level) {
      params.append('level', options.level);
    }
    
    // Add query string to endpoint
    const queryString = params.toString();
    if (queryString) {
      endpoint += `?${queryString}`;
    }
    
    return await this.request('POST', endpoint);
  }
  
  /**
   * Create a memory
   * 
   * @param {Object} memoryData Memory data
   * @returns {Promise<Object>} Created memory
   */
  async createMemory(memoryData) {
    return await this.request('POST', '/memory', memoryData);
  }
  
  /**
   * Get memory by ID
   * 
   * @param {string} memoryId Memory ID
   * @returns {Promise<Object>} Memory data
   */
  async getMemory(memoryId) {
    return await this.request('GET', `/memory/${memoryId}`);
  }
  
  /**
   * Update memory
   * 
   * @param {string} memoryId Memory ID
   * @param {Object} memoryData Memory data
   * @returns {Promise<Object>} Updated memory
   */
  async updateMemory(memoryId, memoryData) {
    return await this.request('PUT', `/memory/${memoryId}`, memoryData);
  }
  
  /**
   * Delete memory
   * 
   * @param {string} memoryId Memory ID
   * @returns {Promise<Object>} Result
   */
  async deleteMemory(memoryId) {
    return await this.request('DELETE', `/memory/${memoryId}`);
  }
  
  /**
   * Get memory visualization
   * 
   * @param {string} visualizationType Visualization type (graph, timeline, tags, etc.)
   * @param {Object} options Visualization options
   * @returns {Promise<Object>} Visualization data
   */
  async getMemoryVisualization(visualizationType, options = {}) {
    if (!this.userId) {
      throw new Error('User ID is required to get memory visualization');
    }
    
    let endpoint = `/memory/visualization/${visualizationType}/${this.userId}`;
    
    // Add query parameters
    const params = new URLSearchParams();
    
    for (const [key, value] of Object.entries(options)) {
      if (Array.isArray(value)) {
        for (const item of value) {
          params.append(key, item);
        }
      } else if (value !== undefined) {
        params.append(key, value);
      }
    }
    
    // Add query string to endpoint
    const queryString = params.toString();
    if (queryString) {
      endpoint += `?${queryString}`;
    }
    
    return await this.request('GET', endpoint);
  }
  
  /**
   * Execute code
   * 
   * @param {Object} codeData Code data
   * @param {string} codeData.code Code to execute
   * @param {string} codeData.language Programming language
   * @returns {Promise<Object>} Execution result
   */
  async executeCode(codeData) {
    return await this.request('POST', '/code/execute', codeData);
  }
  
  /**
   * Query Pickaxe agent
   * 
   * @param {string} agentId Agent ID
   * @param {Object} queryData Query data
   * @param {string} queryData.query User query
   * @param {string} queryData.conversationId Optional conversation ID
   * @returns {Promise<Object>} Agent response
   */
  async queryPickaxeAgent(agentId, queryData) {
    return await this.request('POST', `/pickaxe/agents/${agentId}/query`, queryData);
  }
  
  /**
   * Search Pickaxe knowledge base
   * 
   * @param {string} kbId Knowledge base ID
   * @param {Object} searchData Search data
   * @param {string} searchData.query Search query
   * @param {number} searchData.topK Optional number of results to return
   * @param {number} searchData.threshold Optional similarity threshold
   * @returns {Promise<Object>} Search results
   */
  async searchPickaxeKnowledgeBase(kbId, searchData) {
    return await this.request('POST', `/pickaxe/knowledge-bases/${kbId}/search`, searchData);
  }
}

// Export for both browser and Node.js environments
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
  module.exports = EchoMindClient;
} else {
  window.EchoMindClient = EchoMindClient;
}