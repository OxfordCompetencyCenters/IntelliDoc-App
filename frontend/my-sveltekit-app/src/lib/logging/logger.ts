/**
 * Frontend Logger - Comprehensive Logging for Phase 2 Implementation
 * 
 * Provides comprehensive logging infrastructure that coordinates with backend logging
 * All logs are captured and sent to /logs/frontend_TIMESTAMP.log via console output redirection
 */

export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARNING = 'WARNING',
  ERROR = 'ERROR'
}

export class Logger {
  private static instance: Logger;
  private componentName: string;

  private constructor(componentName: string = 'Frontend') {
    this.componentName = componentName;
  }

  static getInstance(componentName?: string): Logger {
    if (!Logger.instance || componentName) {
      Logger.instance = new Logger(componentName);
    }
    return Logger.instance;
  }

  static getComponentLogger(componentName: string): Logger {
    return new Logger(componentName);
  }

  private formatMessage(level: LogLevel, message: string, data?: any): string {
    const timestamp = new Date().toISOString();
    const dataStr = data ? ` | Data: ${JSON.stringify(data)}` : '';
    return `[${level}] ${timestamp} ${this.componentName} | ${message}${dataStr}`;
  }

  info(message: string, data?: any): void {
    console.log(this.formatMessage(LogLevel.INFO, message, data));
  }

  debug(message: string, data?: any): void {
    console.debug(this.formatMessage(LogLevel.DEBUG, message, data));
  }

  warning(message: string, data?: any): void {
    console.warn(this.formatMessage(LogLevel.WARNING, message, data));
  }

  error(message: string, error?: any): void {
    console.error(this.formatMessage(LogLevel.ERROR, message, error));
  }

  // Template-specific logging methods
  templateAction(action: string, templateId: string, data?: any): void {
    this.info(`Template Action: ${action} for template ${templateId}`, data);
  }

  templateNavigation(from: string, to: string, templateId: string): void {
    this.info(`Template Navigation: ${from} -> ${to} for template ${templateId}`);
  }

  projectAction(action: string, projectId: string, data?: any): void {
    this.info(`Project Action: ${action} for project ${projectId}`, data);
  }

  apiCall(method: string, endpoint: string, data?: any): void {
    this.info(`API Call: ${method} ${endpoint}`, data);
  }

  apiResponse(endpoint: string, status: number, data?: any): void {
    this.info(`API Response: ${endpoint} returned ${status}`, data);
  }

  apiError(endpoint: string, error: any): void {
    this.error(`API Error: ${endpoint} failed`, error);
  }

  componentMount(componentName: string, data?: any): void {
    this.info(`Component Mounted: ${componentName}`, data);
  }

  componentUnmount(componentName: string): void {
    this.info(`Component Unmounted: ${componentName}`);
  }

  userInteraction(action: string, element: string, data?: any): void {
    this.info(`User Interaction: ${action} on ${element}`, data);
  }

  fileOperation(operation: string, fileInfo: any): void {
    this.info(`File Operation: ${operation}`, fileInfo);
  }

  stateChange(storeName: string, oldValue: any, newValue: any): void {
    this.info(`State Change: ${storeName}`, { oldValue, newValue });
  }

  performance(operation: string, duration: number, details?: any): void {
    this.info(`Performance: ${operation} took ${duration}ms`, details);
  }
}

// Export convenience functions for common logging patterns
export const createLogger = (componentName: string) => Logger.getComponentLogger(componentName);
export const getLogger = () => Logger.getInstance();

// Template-specific logger creators
export const createTemplateLogger = (templateId: string, component: string) => 
  Logger.getComponentLogger(`Template.${templateId}.${component}`);

export const createProjectLogger = (projectId: string, component: string) =>
  Logger.getComponentLogger(`Project.${projectId}.${component}`);

export const createUniversalLogger = (component: string) =>
  Logger.getComponentLogger(`Universal.${component}`);
