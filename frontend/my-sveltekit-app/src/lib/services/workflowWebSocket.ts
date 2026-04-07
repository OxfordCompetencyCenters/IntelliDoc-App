/**
 * Workflow WebSocket Service - Real-Time Execution Communication
 * 
 * PHASE 4: Handles real-time communication with workflow execution including:
 * - Live agent message streaming
 * - Human input request/response handling  
 * - Execution status updates
 * - Error reporting and recovery
 */

import { writable, type Writable } from 'svelte/store';

// TypeScript types for Phase 4
export interface AgentMessage {
    id: string;
    agent_name: string;
    agent_type: string;
    content: string;
    message_type: string;
    sequence_number: number;
    timestamp: string;
    response_time_ms?: number;
    token_count?: number;
}

export interface HumanInputRequest {
    request_id: string;
    agent_name: string;
    prompt: string;
    timeout_seconds: number;
    timestamp: string;
}

export interface ExecutionStatus {
    status: 'idle' | 'running' | 'completed' | 'failed' | 'paused';
    message: string;
    progress: number;
    timestamp: string;
}

export interface WorkflowCapabilities {
    real_time_messaging: boolean;
    human_input_support: boolean;
    code_execution: boolean;
    multi_provider_llm: boolean;
    execution_status: boolean;
    error_recovery: boolean;
}

export class WorkflowWebSocketService {
    private ws: WebSocket | null = null;
    private projectId: string = '';
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectInterval = 3000;
    private reconnectTimer: NodeJS.Timeout | null = null;
    
    // Svelte stores for reactive updates
    public messages: Writable<AgentMessage[]> = writable([]);
    public executionStatus: Writable<ExecutionStatus> = writable({
        status: 'idle',
        message: 'Disconnected',
        progress: 0,
        timestamp: new Date().toISOString()
    });
    public connectionStatus: Writable<'disconnected' | 'connecting' | 'connected' | 'error'> = writable('disconnected');
    public capabilities: Writable<WorkflowCapabilities | null> = writable(null);
    public humanInputRequests: Writable<HumanInputRequest[]> = writable([]);
    
    // Event handlers
    private messageHandlers: Map<string, Function> = new Map();
    private humanInputCallback: ((request: HumanInputRequest) => void) | null = null;
    
    constructor() {
        console.log('🤖 Workflow WebSocket Service initialized');
    }
    
    /**
     * Connect to Workflow WebSocket for real-time execution
     */
    async connect(projectId: string): Promise<void> {
        this.projectId = projectId;
        this.connectionStatus.set('connecting');
        
        return new Promise((resolve, reject) => {
            try {
                // Determine WebSocket URL based on environment
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const host = window.location.host; // includes port (e.g., "localhost:5173")
                const wsUrl = `${protocol}//${host}/ws/workflow/${projectId}/`;
                
                console.log(`🔌 Workflow WebSocket connecting to: ${wsUrl}`);
                
                this.ws = new WebSocket(wsUrl);
                
                this.ws.onopen = () => {
                    console.log('✅ Workflow WebSocket connected');
                    this.connectionStatus.set('connected');
                    this.reconnectAttempts = 0;
                    resolve();
                };
                
                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleMessage(data);
                    } catch (error) {
                        console.error('❌ Workflow WebSocket message parse error:', error);
                    }
                };
                
                this.ws.onclose = (event) => {
                    console.log('🔌 Workflow WebSocket closed:', event.code, event.reason);
                    this.connectionStatus.set('disconnected');
                    this.ws = null;
                    
                    // Attempt to reconnect if not a clean close
                    if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                        this.scheduleReconnect();
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('❌ Workflow WebSocket error:', error);
                    this.connectionStatus.set('error');
                    reject(error);
                };
                
                // Connection timeout
                setTimeout(() => {
                    if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
                        this.ws.close();
                        reject(new Error('Workflow WebSocket connection timeout'));
                    }
                }, 10000);
                
            } catch (error) {
                console.error('❌ Workflow WebSocket connection error:', error);
                this.connectionStatus.set('error');
                reject(error);
            }
        });
    }
    
    /**
     * Disconnect from Workflow WebSocket
     */
    disconnect(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }
        
        this.connectionStatus.set('disconnected');
        console.log('🔌 Workflow WebSocket disconnected');
    }
    
    /**
     * Handle incoming WebSocket messages
     */
    private handleMessage(data: any): void {
        console.log('📨 Workflow WebSocket message:', data.type);
        
        switch (data.type) {
            case 'workflow_connected':
                this.handleConnection(data);
                break;
                
            case 'agent_message':
                this.handleAgentMessage(data);
                break;
                
            case 'execution_status':
                this.handleExecutionStatus(data);
                break;
                
            case 'human_input_request':
                this.handleHumanInputRequest(data);
                break;
                
            case 'human_input_acknowledged':
                this.handleHumanInputAcknowledged(data);
                break;
                
            case 'execution_control_acknowledged':
                this.handleExecutionControlAcknowledged(data);
                break;
                
            case 'pong':
                // Handle ping/pong for connection health
                break;
                
            default:
                console.warn('⚠️ Workflow WebSocket unknown message type:', data.type);
        }
        
        // Call custom handlers
        const handler = this.messageHandlers.get(data.type);
        if (handler) {
            handler(data);
        }
    }
    
    /**
     * Handle connection establishment
     */
    private handleConnection(data: any): void {
        console.log('🎉 Workflow connection established with capabilities:', data.capabilities);
        this.capabilities.set(data.capabilities);
        
        this.executionStatus.update(status => ({
            ...status,
            status: 'idle',
            message: 'Connected to real-time workflow execution',
            timestamp: data.timestamp
        }));
    }
    
    /**
     * Handle real-time agent messages
     */
    private handleAgentMessage(data: any): void {
        const message: AgentMessage = {
            id: data.id,
            agent_name: data.agent_name,
            agent_type: data.agent_type,
            content: data.content,
            message_type: data.message_type,
            sequence_number: data.sequence_number,
            timestamp: data.timestamp,
            response_time_ms: data.response_time_ms,
            token_count: data.token_count
        };
        
        this.messages.update(messages => [...messages, message]);
        console.log(`💬 Agent message from ${message.agent_name}: ${message.content.substring(0, 50)}...`);
    }
    
    /**
     * Handle execution status updates
     */
    private handleExecutionStatus(data: any): void {
        const status: ExecutionStatus = {
            status: data.status,
            message: data.message,
            progress: data.progress,
            timestamp: data.timestamp
        };
        
        this.executionStatus.set(status);
        console.log(`📊 Execution status: ${status.status} - ${status.message}`);
    }
    
    /**
     * Handle human input requests
     */
    private handleHumanInputRequest(data: any): void {
        const request: HumanInputRequest = {
            request_id: data.request_id,
            agent_name: data.agent_name,
            prompt: data.prompt,
            timeout_seconds: data.timeout_seconds,
            timestamp: data.timestamp
        };
        
        this.humanInputRequests.update(requests => [...requests, request]);
        
        // Call custom human input callback if set
        if (this.humanInputCallback) {
            this.humanInputCallback(request);
        }
        
        console.log(`👤 Human input requested by ${request.agent_name}: ${request.prompt}`);
    }
    
    /**
     * Handle human input acknowledgment
     */
    private handleHumanInputAcknowledged(data: any): void {
        console.log(`✅ Human input acknowledged for request ${data.request_id}`);
        
        // Remove the request from pending list
        this.humanInputRequests.update(requests => 
            requests.filter(req => req.request_id !== data.request_id)
        );
    }
    
    /**
     * Handle execution control acknowledgment
     */
    private handleExecutionControlAcknowledged(data: any): void {
        console.log(`🎮 Execution control acknowledged: ${data.command} for run ${data.run_id}`);
    }
    
    /**
     * Send human input response
     */
    sendHumanInput(requestId: string, input: string): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = {
                type: 'human_input_response',
                request_id: requestId,
                input: input,
                timestamp: new Date().toISOString()
            };
            
            this.ws.send(JSON.stringify(message));
            console.log(`👤 Sent human input for request ${requestId}: ${input.substring(0, 50)}...`);
        } else {
            console.error('❌ Cannot send human input: WebSocket not connected');
        }
    }
    
    /**
     * Send execution control command
     */
    sendExecutionControl(command: 'pause' | 'resume' | 'stop', runId: string): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = {
                type: 'execution_control',
                command: command,
                run_id: runId,
                timestamp: new Date().toISOString()
            };
            
            this.ws.send(JSON.stringify(message));
            console.log(`🎮 Sent execution control: ${command} for run ${runId}`);
        } else {
            console.error('❌ Cannot send execution control: WebSocket not connected');
        }
    }
    
    /**
     * Send ping to check connection health
     */
    ping(): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'ping',
                timestamp: new Date().toISOString()
            }));
        }
    }
    
    /**
     * Register custom message handler
     */
    onMessage(type: string, handler: Function): void {
        this.messageHandlers.set(type, handler);
    }
    
    /**
     * Set custom human input callback
     */
    onHumanInputRequest(callback: (request: HumanInputRequest) => void): void {
        this.humanInputCallback = callback;
    }
    
    /**
     * Clear all messages
     */
    clearMessages(): void {
        this.messages.set([]);
    }
    
    /**
     * Get current connection state
     */
    isConnected(): boolean {
        return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
    }
    
    /**
     * Schedule reconnection attempt
     */
    private scheduleReconnect(): void {
        this.reconnectAttempts++;
        console.log(`🔄 Scheduling Workflow WebSocket reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
        
        this.reconnectTimer = setTimeout(async () => {
            try {
                await this.connect(this.projectId);
            } catch (error) {
                console.error('❌ Workflow WebSocket reconnect failed:', error);
            }
        }, this.reconnectInterval * this.reconnectAttempts);
    }
}

// Singleton instance for global use
export const workflowWebSocket = new WorkflowWebSocketService();

// Helper function to create a new instance if needed
export function createWorkflowWebSocket(): WorkflowWebSocketService {
    return new WorkflowWebSocketService();
}

