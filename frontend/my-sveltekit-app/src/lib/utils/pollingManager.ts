/**
 * Polling Manager - Prevents aggressive polling and manages intervals properly
 */

export class PollingManager {
  private static intervals: Map<string, number> = new Map();
  private static maxPolls: Map<string, number> = new Map();
  private static pollCounts: Map<string, number> = new Map();

  /**
   * Start polling with automatic cleanup and limits
   */
  static startPolling(
    key: string,
    pollFunction: () => Promise<void>,
    intervalMs: number = 3000,
    maxPolls: number = 20
  ): void {
    // Stop any existing polling for this key
    this.stopPolling(key);
    
    console.log(`🔄 POLLING_MANAGER: Starting polling for '${key}' (${intervalMs}ms, max ${maxPolls} polls)`);
    
    this.maxPolls.set(key, maxPolls);
    this.pollCounts.set(key, 0);
    
    const poll = async () => {
      const currentCount = this.pollCounts.get(key) || 0;
      const maxCount = this.maxPolls.get(key) || maxPolls;
      
      if (currentCount >= maxCount) {
        console.log(`🛑 POLLING_MANAGER: Auto-stopping '${key}' after ${currentCount} polls`);
        this.stopPolling(key);
        return;
      }
      
      try {
        await pollFunction();
        this.pollCounts.set(key, currentCount + 1);
      } catch (error) {
        console.error(`❌ POLLING_MANAGER: Error in '${key}' poll:`, error);
        // Stop polling on repeated errors
        this.stopPolling(key);
      }
    };
    
    // Initial poll
    poll();
    
    // Start interval
    const intervalId = setInterval(poll, intervalMs) as unknown as number;
    this.intervals.set(key, intervalId);
    
    console.log(`✅ POLLING_MANAGER: Polling started for '${key}' (ID: ${intervalId})`);
  }
  
  /**
   * Stop polling for a specific key
   */
  static stopPolling(key: string): void {
    const intervalId = this.intervals.get(key);
    
    if (intervalId) {
      clearInterval(intervalId);
      this.intervals.delete(key);
      this.maxPolls.delete(key);
      this.pollCounts.delete(key);
      console.log(`🛑 POLLING_MANAGER: Stopped polling for '${key}' (ID: ${intervalId})`);
    }
  }
  
  /**
   * Stop all active polling
   */
  static stopAllPolling(): void {
    console.log(`🛑 POLLING_MANAGER: Stopping all ${this.intervals.size} active polls`);
    
    for (const key of this.intervals.keys()) {
      this.stopPolling(key);
    }
  }
  
  /**
   * Get status of all active polling
   */
  static getStatus(): Record<string, any> {
    const status: Record<string, any> = {};
    
    for (const [key, intervalId] of this.intervals.entries()) {
      status[key] = {
        intervalId,
        pollCount: this.pollCounts.get(key) || 0,
        maxPolls: this.maxPolls.get(key) || 0
      };
    }
    
    return status;
  }
}

// Global cleanup on page unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    PollingManager.stopAllPolling();
  });
}