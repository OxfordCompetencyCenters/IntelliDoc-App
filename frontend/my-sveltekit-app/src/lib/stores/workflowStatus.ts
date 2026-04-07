// src/lib/stores/workflowStatus.ts
// Workflow Status Store for Human Input Management (Phase 3 Implementation)

import { writable } from 'svelte/store';
import { humanInputService, type PendingHumanInput } from '../services/humanInputService';

interface WorkflowStatus {
  pendingInputs: PendingHumanInput[];
  isPolling: boolean;
  pollingInterval: number | null;
  lastUpdate: string | null;
  isLoading: boolean;
  error: string | null;
}

function createWorkflowStatusStore() {
  const { subscribe, set, update } = writable<WorkflowStatus>({
    pendingInputs: [],
    isPolling: false,
    pollingInterval: null,
    lastUpdate: null,
    isLoading: false,
    error: null
  });

  return {
    subscribe,

    /**
     * Start polling for pending human inputs with smart management
     */
    startPolling(intervalMs: number = 3000) {
      console.log('🔄 WORKFLOW STATUS STORE: Starting smart polling');
      
      update(state => {
        // Don't start if already polling
        if (state.isPolling && state.pollingInterval) {
          console.log('⚠️ WORKFLOW STATUS STORE: Already polling, skipping start');
          return state;
        }

        // Stop any existing interval first
        if (state.pollingInterval) {
          clearInterval(state.pollingInterval);
        }

        try {
          let consecutiveEmptyPolls = 0;
          const maxEmptyPolls = 10; // Stop after 10 consecutive empty polls (30 seconds)
          
          const intervalId = humanInputService.startPolling(
            (inputs) => {
              update(s => {
                // Track empty polls for auto-stop functionality
                if (inputs.length === 0) {
                  consecutiveEmptyPolls++;
                  
                  // Auto-stop polling after many empty polls to save resources
                  if (consecutiveEmptyPolls >= maxEmptyPolls && s.isPolling) {
                    console.log('🛑 WORKFLOW STATUS STORE: Auto-stopping polling after', consecutiveEmptyPolls, 'empty polls');
                    // Stop polling by clearing interval
                    if (s.pollingInterval) {
                      humanInputService.stopPolling(s.pollingInterval);
                    }
                    return {
                      ...s,
                      pendingInputs: inputs,
                      lastUpdate: new Date().toISOString(),
                      error: null,
                      isLoading: false,
                      isPolling: false,
                      pollingInterval: null
                    };
                  }
                } else {
                  consecutiveEmptyPolls = 0; // Reset counter when inputs found
                }
                
                return {
                  ...s,
                  pendingInputs: inputs,
                  lastUpdate: new Date().toISOString(),
                  error: null,
                  isLoading: false
                };
              });

              // Log significant changes only
              if (inputs.length > 0) {
                console.log(`🔔 WORKFLOW STATUS STORE: ${inputs.length} pending input(s) detected`);
              }
            },
            intervalMs
          );

          console.log('✅ WORKFLOW STATUS STORE: Smart polling started successfully');

          return {
            ...state,
            isPolling: true,
            pollingInterval: intervalId,
            isLoading: true,
            error: null
          };
        } catch (error) {
          console.error('❌ WORKFLOW STATUS STORE: Failed to start polling:', error);
          
          return {
            ...state,
            isPolling: false,
            pollingInterval: null,
            error: `Failed to start polling: ${error.message}`,
            isLoading: false
          };
        }
      });
    },

    /**
     * Stop polling for pending human inputs
     */
    stopPolling() {
      console.log('🛑 WORKFLOW STATUS STORE: Stopping polling');
      
      update(state => {
        if (state.pollingInterval) {
          humanInputService.stopPolling(state.pollingInterval);
        }

        return {
          ...state,
          isPolling: false,
          pollingInterval: null,
          isLoading: false
        };
      });

      console.log('✅ WORKFLOW STATUS STORE: Polling stopped');
    },

    /**
     * Restart polling (useful after workflows complete)
     */
    restartPolling(intervalMs: number = 3000) {
      console.log('🔄 WORKFLOW STATUS STORE: Restarting polling');
      this.stopPolling();
      // Small delay to ensure cleanup completes
      setTimeout(() => this.startPolling(intervalMs), 100);
    },

    /**
     * Manually refresh pending inputs (one-time fetch)
     */
    async refreshInputs() {
      console.log('🔄 WORKFLOW STATUS STORE: Manual refresh requested');
      
      update(state => ({ ...state, isLoading: true, error: null }));

      try {
        const inputs = await humanInputService.getPendingInputs();
        
        update(state => ({
          ...state,
          pendingInputs: inputs,
          lastUpdate: new Date().toISOString(),
          error: null,
          isLoading: false
        }));

        console.log(`✅ WORKFLOW STATUS STORE: Manual refresh completed - ${inputs.length} pending input(s)`);
        
        return inputs;
      } catch (error) {
        console.error('❌ WORKFLOW STATUS STORE: Manual refresh failed:', error);
        
        update(state => ({
          ...state,
          error: `Failed to refresh: ${error.message}`,
          isLoading: false
        }));

        throw error;
      }
    },

    /**
     * Submit human input and remove from pending list
     */
    async submitInput(executionId: string, humanInput: string, options?: { action?: string }) {
      const action = options?.action || 'submit';
      console.log('📝 WORKFLOW STATUS STORE: Submitting input for execution', executionId, 'with action:', action);
      
      update(state => ({ ...state, isLoading: true, error: null }));

      try {
        const result = await humanInputService.submitInput({
          execution_id: executionId,
          human_input: humanInput,
          action: action
        });

        // For iteration, don't remove from pending list as workflow will continue
        // Only remove for final submission
        if (action !== 'iterate') {
          update(state => ({
            ...state,
            pendingInputs: state.pendingInputs.filter(input => input.execution_id !== executionId),
            lastUpdate: new Date().toISOString(),
            isLoading: false,
            error: null
          }));
        } else {
          update(state => ({
            ...state,
            lastUpdate: new Date().toISOString(),
            isLoading: false,
            error: null
          }));
        }

        console.log('✅ WORKFLOW STATUS STORE: Input submitted successfully with action:', action);
        
        return result;
      } catch (error) {
        console.error('❌ WORKFLOW STATUS STORE: Input submission failed:', error);
        
        update(state => ({
          ...state,
          error: `Failed to submit input: ${error.message}`,
          isLoading: false
        }));

        throw error;
      }
    },

    /**
     * Check if a specific execution is awaiting input
     */
    isExecutionPending(executionId: string): boolean {
      let isPending = false;
      
      subscribe(state => {
        isPending = state.pendingInputs.some(input => input.execution_id === executionId);
      })();

      return isPending;
    },

    /**
     * Get input context for a specific execution
     */
    getExecutionContext(executionId: string): PendingHumanInput | null {
      let context: PendingHumanInput | null = null;
      
      subscribe(state => {
        context = state.pendingInputs.find(input => input.execution_id === executionId) || null;
      })();

      return context;
    },

    /**
     * Clear all state and stop polling
     */
    reset() {
      console.log('🧹 WORKFLOW STATUS STORE: Resetting state');
      
      update(state => {
        if (state.pollingInterval) {
          humanInputService.stopPolling(state.pollingInterval);
        }

        return {
          pendingInputs: [],
          isPolling: false,
          pollingInterval: null,
          lastUpdate: null,
          isLoading: false,
          error: null
        };
      });

      console.log('✅ WORKFLOW STATUS STORE: State reset complete');
    },

    /**
     * Clear error state
     */
    clearError() {
      update(state => ({ ...state, error: null }));
    },

    /**
     * Get current state snapshot (for debugging)
     */
    getSnapshot(): WorkflowStatus {
      let snapshot: WorkflowStatus;
      
      subscribe(state => {
        snapshot = { ...state };
      })();

      return snapshot!;
    }
  };
}

// Export singleton store instance
export const workflowStatus = createWorkflowStatusStore();

// Export derived stores for convenience
import { derived } from 'svelte/store';

export const pendingInputsCount = derived(
  workflowStatus,
  $status => $status.pendingInputs.length
);

export const hasUrgentInputs = derived(
  workflowStatus,
  $status => {
    const now = new Date();
    return $status.pendingInputs.some(input => {
      const requestedAt = new Date(input.requested_at);
      const minutesWaiting = (now.getTime() - requestedAt.getTime()) / (1000 * 60);
      return minutesWaiting > 5; // Consider urgent if waiting more than 5 minutes
    });
  }
);

export const isWorkflowStatusActive = derived(
  workflowStatus,
  $status => $status.isPolling && !$status.error
);

// Utility functions for components
export function formatWaitingTime(requestedAt: string): string {
  const now = new Date();
  const requested = new Date(requestedAt);
  const diffMs = now.getTime() - requested.getTime();
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  
  if (diffMinutes < 1) {
    return 'Just now';
  } else if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
  } else {
    const diffHours = Math.floor(diffMinutes / 60);
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  }
}

export function getInputUrgencyLevel(requestedAt: string): 'low' | 'medium' | 'high' {
  const now = new Date();
  const requested = new Date(requestedAt);
  const minutesWaiting = (now.getTime() - requested.getTime()) / (1000 * 60);
  
  if (minutesWaiting > 30) return 'high';
  if (minutesWaiting > 10) return 'medium';
  return 'low';
}

console.log('🏪 WORKFLOW STATUS STORE: Store module loaded and ready');
