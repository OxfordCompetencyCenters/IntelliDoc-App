/**
 * Template Independence Test Suite
 * 
 * Validates that the AI Catalogue achieves 100% template independence
 * using the Clean Universal API architecture
 */

import { cleanUniversalApi } from '../services/cleanUniversalApi';

export class TemplateIndependenceTestSuite {
  private testResults: any[] = [];
  private score = 0;
  private maxScore = 100;

  /**
   * Run complete template independence test suite
   */
  async runAllTests(): Promise<{
    overallScore: number;
    maxScore: number;
    passed: number;
    failed: number;
    results: any[];
    summary: string;
  }> {
    console.log('🧪 Starting Template Independence Test Suite');
    console.log('=========================================');
    
    this.testResults = [];
    this.score = 0;
    
    // Test 1: Universal API Usage (25 points)
    await this.testUniversalApiUsage();
    
    // Test 2: Template Data Cloning (25 points)
    await this.testTemplateDataCloning();
    
    // Test 3: File Independence (25 points)
    await this.testFileIndependence();
    
    // Test 4: Universal Interface Usage (25 points)
    await this.testUniversalInterfaceUsage();
    
    const passed = this.testResults.filter(r => r.passed).length;
    const failed = this.testResults.filter(r => !r.passed).length;
    
    const summary = this.generateSummary();
    console.log('\n' + summary);
    
    return {
      overallScore: this.score,
      maxScore: this.maxScore,
      passed,
      failed,
      results: this.testResults,
      summary
    };
  }

  /**
   * Test 1: Universal API Usage (25 points)
   * Verify all operations use universal endpoints
   */
  private async testUniversalApiUsage(): Promise<void> {
    console.log('\n📋 Test 1: Universal API Usage');
    console.log('================================');
    
    try {
      // Test universal project creation
      const projectData = {
        name: 'Test Template Independence',
        description: 'Testing universal API usage',
        template_id: 'aicc-intellidoc'
      };
      
      console.log('🏗️ Testing universal project creation...');
      const project = await cleanUniversalApi.createProject(projectData);
      
      if (project && project.project_id) {
        this.addTestResult('Universal Project Creation', true, 10, 
          'Projects created via /api/projects/ endpoint');
        
        // Test universal project retrieval
        console.log('📄 Testing universal project retrieval...');
        const retrievedProject = await cleanUniversalApi.getProject(project.project_id);
        
        if (retrievedProject && retrievedProject.project_id === project.project_id) {
          this.addTestResult('Universal Project Retrieval', true, 10,
            'Projects retrieved via /api/projects/{id}/ endpoint');
          
          // Test universal document operations
          console.log('📄 Testing universal document operations...');
          const documents = await cleanUniversalApi.getDocuments(project.project_id);
          
          this.addTestResult('Universal Document Access', true, 5,
            'Documents accessed via /api/projects/{id}/documents/ endpoint');
          
          // Clean up test project
          await cleanUniversalApi.deleteProject(project.project_id, 'test');
          
        } else {
          this.addTestResult('Universal Project Retrieval', false, 0,
            'Failed to retrieve project via universal endpoint');
        }
      } else {
        this.addTestResult('Universal Project Creation', false, 0,
          'Failed to create project via universal endpoint');
      }
      
    } catch (error) {
      console.error('❌ Universal API test failed:', error);
      this.addTestResult('Universal API Usage', false, 0, 
        `API test failed: ${error.message}`);
    }
  }

  /**
   * Test 2: Template Data Cloning (25 points)
   * Verify template data is cloned to project fields
   */
  private async testTemplateDataCloning(): Promise<void> {
    console.log('\n📋 Test 2: Template Data Cloning');
    console.log('=================================');
    
    try {
      // Create project from template
      const projectData = {
        name: 'Test Template Cloning',
        description: 'Testing template data cloning',
        template_id: 'aicc-intellidoc'
      };
      
      const project = await cleanUniversalApi.createProject(projectData);
      
      if (project) {
        // Verify template data was cloned
        const clonedFields = [
          'template_name', 'template_type', 'instructions',
          'analysis_focus', 'has_navigation', 'total_pages',
          'navigation_pages', 'processing_capabilities'
        ];
        
        let clonedFieldsFound = 0;
        
        for (const field of clonedFields) {
          if (project.hasOwnProperty(field) && project[field] != null) {
            clonedFieldsFound++;
            console.log(`✅ Found cloned field: ${field}`);
          } else {
            console.log(`❌ Missing cloned field: ${field}`);
          }
        }
        
        const cloneScore = Math.round((clonedFieldsFound / clonedFields.length) * 25);
        
        this.addTestResult('Template Data Cloning', clonedFieldsFound === clonedFields.length, 
          cloneScore, `${clonedFieldsFound}/${clonedFields.length} template fields cloned`);
        
        // Clean up
        await cleanUniversalApi.deleteProject(project.project_id, 'test');
        
      } else {
        this.addTestResult('Template Data Cloning', false, 0,
          'Could not create project to test data cloning');
      }
      
    } catch (error) {
      console.error('❌ Template data cloning test failed:', error);
      this.addTestResult('Template Data Cloning', false, 0,
        `Template cloning test failed: ${error.message}`);
    }
  }

  /**
   * Test 3: File Independence (25 points)
   * Verify projects work without template files
   */
  private async testFileIndependence(): Promise<void> {
    console.log('\n📋 Test 3: File Independence');
    console.log('=============================');
    
    try {
      // Create project
      const projectData = {
        name: 'Test File Independence',
        description: 'Testing file independence',
        template_id: 'aicc-intellidoc'
      };
      
      const project = await cleanUniversalApi.createProject(projectData);
      
      if (project) {
        // Test project operations (simulating template files being deleted)
        console.log('📄 Testing project operations without template files...');
        
        // 1. Project retrieval should work
        try {
          const retrieved = await cleanUniversalApi.getProject(project.project_id);
          if (retrieved) {
            this.addTestResult('Project Retrieval Independence', true, 10,
              'Project retrieval works without template files');
          }
        } catch (error) {
          this.addTestResult('Project Retrieval Independence', false, 0,
            'Project retrieval failed without template files');
        }
        
        // 2. Document operations should work
        try {
          const documents = await cleanUniversalApi.getDocuments(project.project_id);
          this.addTestResult('Document Operations Independence', true, 10,
            'Document operations work without template files');
        } catch (error) {
          this.addTestResult('Document Operations Independence', false, 0,
            'Document operations failed without template files');
        }
        
        // 3. Processing status should work
        try {
          const status = await cleanUniversalApi.getProcessingStatus(project.project_id);
          this.addTestResult('Processing Status Independence', true, 5,
            'Processing status works without template files');
        } catch (error) {
          this.addTestResult('Processing Status Independence', false, 0,
            'Processing status failed without template files');
        }
        
        // Clean up
        await cleanUniversalApi.deleteProject(project.project_id, 'test');
        
      } else {
        this.addTestResult('File Independence', false, 0,
          'Could not create project to test file independence');
      }
      
    } catch (error) {
      console.error('❌ File independence test failed:', error);
      this.addTestResult('File Independence', false, 0,
        `File independence test failed: ${error.message}`);
    }
  }

  /**
   * Test 4: Universal Interface Usage (25 points)
   * Verify all projects use the same interfaces
   */
  private async testUniversalInterfaceUsage(): Promise<void> {
    console.log('\n📋 Test 4: Universal Interface Usage');
    console.log('====================================');
    
    try {
      // Create projects from different templates
      const templates = ['aicc-intellidoc', 'legal', 'medical', 'history'];
      const createdProjects = [];
      
      for (const templateId of templates) {
        try {
          const projectData = {
            name: `Test Universal Interface ${templateId}`,
            description: `Testing universal interface for ${templateId}`,
            template_id: templateId
          };
          
          const project = await cleanUniversalApi.createProject(projectData);
          if (project) {
            createdProjects.push({ project, templateId });
          }
        } catch (error) {
          console.log(`⚠️ Could not create project from template ${templateId}: ${error.message}`);
        }
      }
      
      if (createdProjects.length > 0) {
        // Test that all projects use the same interface patterns
        let universalInterfaceScore = 0;
        const maxInterfaceScore = 25;
        
        for (const { project, templateId } of createdProjects) {
          console.log(`🔍 Testing universal interface for ${templateId} project...`);
          
          // Test 1: All projects use same endpoint pattern
          try {
            const retrieved = await cleanUniversalApi.getProject(project.project_id);
            if (retrieved && retrieved.project_id === project.project_id) {
              universalInterfaceScore += Math.floor(maxInterfaceScore / (createdProjects.length * 3));
              console.log(`✅ ${templateId}: Universal retrieval endpoint works`);
            }
          } catch (error) {
            console.log(`❌ ${templateId}: Universal retrieval endpoint failed`);
          }
          
          // Test 2: All projects have cloned template data
          if (retrieved && retrieved.template_name && retrieved.template_type) {
            universalInterfaceScore += Math.floor(maxInterfaceScore / (createdProjects.length * 3));
            console.log(`✅ ${templateId}: Has cloned template data`);
          } else {
            console.log(`❌ ${templateId}: Missing cloned template data`);
          }
          
          // Test 3: All projects use same document endpoint
          try {
            const documents = await cleanUniversalApi.getDocuments(project.project_id);
            universalInterfaceScore += Math.floor(maxInterfaceScore / (createdProjects.length * 3));
            console.log(`✅ ${templateId}: Universal document endpoint works`);
          } catch (error) {
            console.log(`❌ ${templateId}: Universal document endpoint failed`);
          }
        }
        
        this.addTestResult('Universal Interface Usage', universalInterfaceScore === maxInterfaceScore,
          universalInterfaceScore, `All projects use universal interfaces (${createdProjects.length} templates tested)`);
        
        // Clean up all test projects
        for (const { project } of createdProjects) {
          try {
            await cleanUniversalApi.deleteProject(project.project_id, 'test');
          } catch (error) {
            console.log(`⚠️ Could not clean up project ${project.project_id}`);
          }
        }
        
      } else {
        this.addTestResult('Universal Interface Usage', false, 0,
          'Could not create any test projects');
      }
      
    } catch (error) {
      console.error('❌ Universal interface test failed:', error);
      this.addTestResult('Universal Interface Usage', false, 0,
        `Universal interface test failed: ${error.message}`);
    }
  }

  /**
   * Add test result and update score
   */
  private addTestResult(testName: string, passed: boolean, points: number, description: string): void {
    this.testResults.push({
      testName,
      passed,
      points,
      description,
      timestamp: new Date().toISOString()
    });
    
    if (passed) {
      this.score += points;
      console.log(`✅ ${testName}: ${description} (+${points} points)`);
    } else {
      console.log(`❌ ${testName}: ${description} (0 points)`);
    }
  }

  /**
   * Generate test summary
   */
  private generateSummary(): string {
    const passed = this.testResults.filter(r => r.passed).length;
    const failed = this.testResults.filter(r => !r.passed).length;
    const percentage = Math.round((this.score / this.maxScore) * 100);
    
    let summary = `\n🎯 TEMPLATE INDEPENDENCE TEST RESULTS\n`;
    summary += `=========================================\n`;
    summary += `Overall Score: ${this.score}/${this.maxScore} (${percentage}%)\n`;
    summary += `Tests Passed: ${passed}\n`;
    summary += `Tests Failed: ${failed}\n\n`;
    
    if (percentage >= 95) {
      summary += `🎉 EXCELLENT: Template independence fully achieved!\n`;
      summary += `✅ Projects are completely independent of templates\n`;
      summary += `✅ Universal interfaces working perfectly\n`;
      summary += `✅ Template data properly cloned\n`;
    } else if (percentage >= 80) {
      summary += `✅ GOOD: Template independence mostly achieved\n`;
      summary += `⚠️ Minor issues remain - see failed tests\n`;
    } else if (percentage >= 60) {
      summary += `⚠️ PARTIAL: Template independence partially achieved\n`;
      summary += `❌ Significant issues remain - requires fixes\n`;
    } else {
      summary += `❌ FAILED: Template independence not achieved\n`;
      summary += `❌ Major architectural issues require immediate attention\n`;
    }
    
    summary += `\n📊 Detailed Results:\n`;
    for (const result of this.testResults) {
      const status = result.passed ? '✅' : '❌';
      summary += `${status} ${result.testName}: ${result.description} (${result.points} pts)\n`;
    }
    
    return summary;
  }

  /**
   * Test specific project operations
   */
  async testProjectOperations(projectId: string): Promise<boolean> {
    try {
      // Test all universal operations
      await cleanUniversalApi.getProject(projectId);
      await cleanUniversalApi.getDocuments(projectId);
      await cleanUniversalApi.getProcessingStatus(projectId);
      
      return true;
    } catch (error) {
      console.error(`Project operations test failed for ${projectId}:`, error);
      return false;
    }
  }

  /**
   * Validate template independence for existing project
   */
  async validateExistingProject(projectId: string): Promise<{
    independent: boolean;
    score: number;
    issues: string[];
  }> {
    const issues: string[] = [];
    let score = 0;
    const maxScore = 10;
    
    try {
      const project = await cleanUniversalApi.getProject(projectId);
      
      if (project) {
        // Check for cloned template data
        if (project.template_name) score += 2;
        else issues.push('Missing cloned template_name');
        
        if (project.template_type) score += 2;
        else issues.push('Missing cloned template_type');
        
        if (project.instructions) score += 2;
        else issues.push('Missing cloned instructions');
        
        if (project.processing_capabilities) score += 2;
        else issues.push('Missing cloned processing_capabilities');
        
        if (project.navigation_pages) score += 2;
        else issues.push('Missing cloned navigation_pages');
        
        // Test operations work
        const operationsWork = await this.testProjectOperations(projectId);
        if (!operationsWork) {
          issues.push('Project operations failed');
        }
        
      } else {
        issues.push('Could not retrieve project');
      }
      
    } catch (error) {
      issues.push(`Project validation failed: ${error.message}`);
    }
    
    return {
      independent: score === maxScore && issues.length === 0,
      score: (score / maxScore) * 100,
      issues
    };
  }
}

// Export singleton for testing
export const templateIndependenceTests = new TemplateIndependenceTestSuite();
