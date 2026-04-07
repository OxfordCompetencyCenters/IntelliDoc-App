// src/lib/services/humanInputService.ts
// Human Input API Service for UserProxyAgent Phase 3 Implementation

import api from './api';

export interface PendingHumanInput {
  execution_id: string;
  workflow_name: string;
  agent_name: string;
  agent_id: string;
  requested_at: string;
  context: {
    agent_id: string;
    input_sources: InputSource[];
    input_count: number;
    primary_input: string;
  };
  conversation_history: string;
}

export interface InputSource {
  name: string;
  type: string;
  content: string;
  priority: number;
}

export interface HumanInputSubmission {
  execution_id: string;
  human_input: string;
  action?: string;
}

export interface HumanInputInteraction {
  id: number;
  execution_id: string;
  workflow_name: string;
  agent_name: string;
  human_response: string;
  response_time: string;
  input_context_summary: string;
  requested_at: string;
  created_at: string;
  workflow_resumed: boolean;
  processed_successfully: boolean;
}

class HumanInputService {
  private readonly baseUrl = '/agent-orchestration/human-input';

  /**
   * Get all workflows currently awaiting human input for the authenticated user
   */
  async getPendingInputs(): Promise<PendingHumanInput[]> {
    try {
      const response = await api.get(`${this.baseUrl}/pending/`);
      const data = response.data || response;
      
      const pendingInputs = data.pending_inputs || [];
      
      // Only log when there are actually pending inputs to reduce console noise
      if (pendingInputs.length > 0) {
        console.log(`✅ HUMAN_INPUT_SERVICE: Retrieved ${pendingInputs.length} pending inputs`);
        console.log('📋 HUMAN_INPUT_SERVICE: Pending inputs details:', 
          pendingInputs.map(input => ({
            execution_id: input.execution_id?.slice(-8),
            agent_name: input.agent_name,
            workflow_name: input.workflow_name,
            requested_at: input.requested_at
          }))
        );
      }
      
      return pendingInputs;
    } catch (error) {
      console.error('❌ HUMAN_INPUT_SERVICE: Failed to get pending inputs:', error);
      
      // Enhanced error handling
      if (error.response?.status === 401) {
        throw new Error('Authentication required to access pending inputs');
      } else if (error.response?.status === 403) {
        throw new Error('You do not have permission to access pending inputs');
      } else if (error.response?.status === 404) {
        throw new Error('Human input service not available');
      }
      
      throw new Error(`Failed to retrieve pending inputs: ${error.message || 'Unknown error'}`);
    }
  }

  /**
   * Submit human input to resume a paused workflow
   */
  async submitInput(submission: HumanInputSubmission): Promise<any> {
    try {
      console.log('📝 HUMAN_INPUT_SERVICE: Starting input submission');
      console.log('📋 HUMAN_INPUT_SERVICE: Submission details:', {
        execution_id: submission.execution_id?.slice(-8),
        input_length: submission.human_input?.length || 0,
        input_preview: submission.human_input?.slice(0, 100) + '...',
        timestamp: new Date().toISOString()
      });
      
      // Validate input
      if (!submission.execution_id?.trim()) {
        console.error('❌ HUMAN_INPUT_SERVICE: Missing execution ID');
        throw new Error('Execution ID is required');
      }
      
      if (!submission.human_input?.trim()) {
        console.error('❌ HUMAN_INPUT_SERVICE: Empty human input');
        throw new Error('Human input cannot be empty');
      }
      
      const requestData = {
        execution_id: submission.execution_id,
        human_input: submission.human_input.trim(),
        action: submission.action || 'submit'
      };
      
      console.log('🌐 HUMAN_INPUT_SERVICE: Sending POST request to submit endpoint');
      console.log('🌐 HUMAN_INPUT_SERVICE: Request data:', {
        execution_id: requestData.execution_id.slice(-8),
        input_length: requestData.human_input.length,
        action: requestData.action
      });
      
      const response = await api.post(`${this.baseUrl}/submit/`, requestData);
      
      console.log('📦 HUMAN_INPUT_SERVICE: Response received:', {
        status: response?.status,
        statusText: response?.statusText,
        hasData: !!response?.data
      });
      
      const result = response.data || response;
      
      console.log('✅ HUMAN_INPUT_SERVICE: Input submitted successfully');
      console.log('🎉 HUMAN_INPUT_SERVICE: Success result:', {
        status: result?.status,
        message: result?.message,
        execution_id: result?.execution_id?.slice(-8)
      });
      
      return result;
    } catch (error) {
      console.error('❌ HUMAN_INPUT_SERVICE: Failed to submit input:', error);
      console.error('❌ HUMAN_INPUT_SERVICE: Submit error details:', {
        message: error?.message,
        status: error?.response?.status,
        statusText: error?.response?.statusText,
        responseData: error?.response?.data,
        url: `${this.baseUrl}/submit/`,
        execution_id: submission?.execution_id?.slice(-8),
        timestamp: new Date().toISOString()
      });
      
      // Enhanced error handling with specific messages
      if (error.response?.status === 400) {
        const errorData = error.response.data;
        throw new Error(errorData?.error || 'Invalid input data provided');
      } else if (error.response?.status === 404) {
        throw new Error('Workflow execution not found or not awaiting input');
      } else if (error.response?.status === 409) {
        throw new Error('Workflow has already been resumed or completed');
      }
      
      throw new Error(`Failed to submit human input: ${error.message || 'Unknown error'}`);
    }
  }

  /**
   * Get history of human input interactions for the authenticated user
   */
  async getInteractionHistory(): Promise<HumanInputInteraction[]> {
    try {
      console.log('📚 HUMAN INPUT SERVICE: Fetching interaction history');
      
      const response = await api.get(`${this.baseUrl}/history/`);
      const data = response.data || response;
      
      const interactions = data.interactions || [];
      
      console.log(`📚 HUMAN INPUT SERVICE: Retrieved ${interactions.length} historical interactions`);
      
      return interactions;
    } catch (error) {
      console.error('❌ HUMAN INPUT SERVICE: Failed to get interaction history:', error);
      throw new Error(`Failed to retrieve interaction history: ${error.message || 'Unknown error'}`);
    }
  }

  /**
   * Start polling for pending human inputs with smart polling logic
   * Returns the interval ID for cleanup
   */
  startPolling(
    callback: (inputs: PendingHumanInput[]) => void, 
    intervalMs: number = 3000
  ): number {
    console.log(`🔄 HUMAN_INPUT_SERVICE: Starting smart polling with ${intervalMs}ms interval`);
    
    let consecutiveEmptyPolls = 0;
    let lastInputCount = 0;
    
    const pollInputs = async () => {
      try {
        const inputs = await this.getPendingInputs();
        callback(inputs);
        
        // Only log when inputs change or when there are inputs
        if (inputs.length !== lastInputCount) {
          if (inputs.length > 0) {
            console.log(`🔔 HUMAN_INPUT_SERVICE: Poll found ${inputs.length} pending input(s)`);
            consecutiveEmptyPolls = 0;
          } else if (lastInputCount > 0) {
            console.log('🧹 HUMAN_INPUT_SERVICE: No more pending inputs detected');
          }
          lastInputCount = inputs.length;
        }
        
        if (inputs.length === 0) {
          consecutiveEmptyPolls++;
        }
        
      } catch (error) {
        console.error('❌ HUMAN_INPUT_SERVICE: Polling error:', error);
        callback([]);
        consecutiveEmptyPolls++;
      }
    };

    // Initial call
    pollInputs();

    // Start interval polling
    const intervalId = setInterval(pollInputs, intervalMs) as unknown as number;
    
    console.log(`✅ HUMAN_INPUT_SERVICE: Smart polling started with interval ID ${intervalId}`);
    
    return intervalId;
  }

  /**
   * Stop polling for pending inputs
   */
  stopPolling(intervalId: number): void {
    if (intervalId) {
      console.log(`🛑 HUMAN_INPUT_SERVICE: Stopping polling for interval ID ${intervalId}`);
      clearInterval(intervalId);
      console.log(`✅ HUMAN_INPUT_SERVICE: Polling stopped successfully`);
    } else {
      console.warn('⚠️ HUMAN_INPUT_SERVICE: No interval ID provided for stopping polling');
    }
  }

  /**
   * Check if a specific workflow execution is awaiting human input
   */
  async isExecutionAwaitingInput(executionId: string): Promise<boolean> {
    try {
      const pendingInputs = await this.getPendingInputs();
      return pendingInputs.some(input => input.execution_id === executionId);
    } catch (error) {
      console.error('❌ HUMAN INPUT SERVICE: Failed to check execution status:', error);
      return false;
    }
  }

  /**
   * Get input context for a specific execution
   */
  async getExecutionInputContext(executionId: string): Promise<PendingHumanInput | null> {
    try {
      const pendingInputs = await this.getPendingInputs();
      return pendingInputs.find(input => input.execution_id === executionId) || null;
    } catch (error) {
      console.error('❌ HUMAN INPUT SERVICE: Failed to get execution context:', error);
      return null;
    }
  }
}

// Export singleton instance
export const humanInputService = new HumanInputService();
export default humanInputService;
