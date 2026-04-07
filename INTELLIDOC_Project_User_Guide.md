## IntelliDoc Project User Guide

![AI Competency Centre – University of Oxford](documentation_images/image.png)

### Quick Start (5 Steps)

1. Open the IntelliDoc platform in your browser and log in.  
2. From the dashboard, click **AICC‑IntelliDoc**.  
3. Click **Create New Project**, enter a name and description, and choose the **AICC IntelliDoc V2** template.  
4. Upload your documents on the **Overview / Project Documents** page and click **Start Processing**.  
5. Design your workflow in **Agent Orchestration**, optionally enable **DocAware**, then **Evaluate**, **Deploy**, and monitor in **Activity Tracker**.

---

### Introduction & Prerequisites

IntelliDoc is a platform that lets you build AI assistants that can read and reason over your own documents. You do this by creating **projects**, uploading documents, and designing **workflows** made of different **agents** that collaborate to answer questions.

- **What is a project?**  
  A project is a self‑contained workspace that holds:
  - Your documents  
  - Your AI workflows (agent orchestration)  
  - Your API keys and configuration  
  - Your evaluations, deployments, and activity history  

  This means you can safely create multiple projects (for different teams, customers, or use cases) without them interfering with each other.

- **What you need before you start**
  - A valid user account for the IntelliDoc platform.
  - The platform URL:
    - **Deployed environment**: `https://aicc.uksouth.cloudapp.azure.com/login`.
  - (Optional but recommended) API keys for your preferred AI providers (for example, OpenAI, Anthropic, Google). These can be added per project later.

![Dashboard login](documentation_images/screenshot_dashboard_login.png)  
Suggested content: Login screen with the main dashboard visible after login.

---

### Getting Started: Accessing the Dashboard

#### Opening IntelliDoc

- In your browser, go to:
  - **Deployed environment**: `https://aicc.uksouth.cloudapp.azure.com/login`.
- Log in with your username and password (or single sign‑on, if configured).

After logging in, you will land on the **Dashboard**. This page shows different features as tiles or cards.

#### Finding AICC‑IntelliDoc

- On the dashboard, look for the tile labeled **“AICC‑IntelliDoc”**.
- Click this tile to open the IntelliDoc feature area where you manage your projects.

![Dashboard with AICC‑IntelliDoc tile](documentation_images/screenshot_dashboard_intellidoc_tile.png)  
Suggested content: Dashboard page with the AICC‑IntelliDoc tile clearly highlighted.

---

### Creating a New Project (AICC IntelliDoc V2)

When you open AICC‑IntelliDoc, you will see a list of existing projects (if any) and a button to create a new one.

#### Project list

- The **project list** shows:
  - Project name  
  - Short description  
  - Status or last updated information (if available)  
- You can click any project card to open that project’s workspace.

![IntelliDoc project list](documentation_images/screenshot_project_list.png)  
Suggested content: IntelliDoc project list with several example projects and the Create New Project button visible.

#### Creating a project with the AICC IntelliDoc V2 template

1. Click **Create New Project**.  
   A dialog or panel will appear asking for project details.
2. Fill in:
   - **Project Name** – a clear, human‑readable name (for example, “Customer Support Docs – Europe”).  
   - **Description** – a short explanation of what this project is for.  
3. Choose the **Template**:
   - Select **“AICC IntelliDoc V2”** from the template dropdown or template list.
4. Click **Create** (or **Save**) to confirm.

After a moment, the new project will be created and you will be taken into the project workspace.

**What the AICC IntelliDoc V2 template does for you**

- Pre‑configures the left‑hand navigation (Overview, Agent Orchestration, Evaluation, Deploy, Activity Tracker).
- Sets reasonable defaults for processing capabilities and workflow structure so you can get started quickly.

**Multiple projects are independent**

- Each project has its own documents, workflows, API keys, and deployments.
- Actions in one project (for example, uploading or processing documents) do **not** interfere with other projects.

![Create New Project dialog](documentation_images/screenshot_project_create_modal.png)  
Suggested content: Create New Project dialog with name, description, and the AICC IntelliDoc V2 template selected.

---

### Understanding the Project Workspace Layout

Once you open a project, you will see a dedicated workspace just for that project.

- The **left‑hand navigation** includes:
  - **Overview / Project Documents**  
  - **Agent Orchestration**  
  - **Evaluation**  
  - **Deploy**  
  - **Activity Tracker**  
- The main area on the right changes depending on which section you select.

![Project workspace navigation](documentation_images/screenshot_project_overview_nav.png)  
Suggested content: Open project showing the left navigation and the Overview / Project Documents page.

#### Navigation overview

![Navigation overview](documentation_images/image_copy.png)

---

### Managing Documents (Overview / Project Documents)

The **Overview / Project Documents** section is where you upload and manage the documents that your AI agents will use.

#### What kinds of documents can I upload?

Depending on your configuration, you can upload common document formats such as:

- PDF files  
- Word documents  
- PowerPoint presentations  
- Text files or similar formats  

These documents are used as the knowledge base for your project. When DocAware is enabled in your workflows, the AI can search and read these documents to answer questions.

#### Uploading documents

On the Overview / Project Documents page, you will generally see several options:

- **Select Files** – Choose one or more files from your computer.  
- **Select Folder** – Select a folder and upload all documents inside it (supported browsers only).  
- **Upload Zip** – Upload a ZIP file that contains multiple documents.  
- **Drag & Drop** – Drag files or folders from your desktop into the upload area (if supported by your browser).

Typical flow:

1. Click **Select Files** (or **Select Folder** / **Upload Zip**).  
2. Choose the files or folders you want to add.  
3. Confirm to start the upload.  
4. Wait for the upload to finish. You should see the documents listed in the table or list.

**Screenshots:**

- ![Documents page empty state](documentation_images/screenshot_documents_empty_state.png)  
  Suggested content: Project Documents page before any documents are uploaded.
- ![Documents page after upload](documentation_images/screenshot_documents_after_upload.png)  
  Suggested content: List of uploaded documents with file names and statuses visible.

#### Starting document processing

Uploading makes the files available to the platform, but to let the AI **understand** them, they must be processed (indexed).

- Click the **Start Processing** button when you are ready.  
- The system will:
  - Break documents into smaller chunks.  
  - Generate vector representations (embeddings).  
  - Store them in a dedicated index for this project.  

While processing is running:

- You may see a progress indicator or status updates.
- You can continue working in other sections or even in other projects.
- Each project’s processing is independent and does not slow down others, except for normal shared system limits.

Once processing is complete, the documents are ready to be used by DocAware workflows.

![Start Processing documents](documentation_images/screenshot_documents_start_processing.png)  
Suggested content: Overview / Project Documents page with the Start Processing button highlighted and some documents listed.

---

### Project‑Specific API Key Management

Some AI features require external API keys (for example, to call OpenAI or other model providers). IntelliDoc lets you manage these **per project**.

#### Why per‑project API keys?

- Different projects may need different providers or models.  
- You might separate keys by client, environment, or cost center.  
- Storing keys per project keeps configuration clean and reduces the risk of accidental cross‑use.

#### Adding or updating API keys

1. In your project workspace, go to the **Overview / Project Documents** (or the section where the **API Key Management** button appears).  
2. Click **API Key Management**.  
3. In the dialog:
   - Choose the provider (for example, OpenAI, Anthropic, Google).  
   - Paste your API key.  
   - Save the changes.
4. The keys are stored securely and used only within this project.

**Safety tips**

- Treat API keys like passwords. Do not share them publicly.  
- Use different keys for development and production if possible.  
- If you suspect a key is compromised, rotate it (create a new key and update it here).

![API Key Management dialog](documentation_images/screenshot_api_key_management_modal.png)  
Suggested content: API Key Management dialog with provider dropdown and key fields.

---

### Designing Workflows with Agent Orchestration

The **Agent Orchestration** section lets you design how different agents (AI components) will work together to answer questions.

#### Key concepts in simple terms

- **Workflow** – A visual flowchart of how a conversation is handled from start to finish.  
- **Agent** – A role in the workflow, such as:
  - An AI assistant that answers questions.  
  - A user proxy that represents the human user in the system.  
  - A manager that delegates tasks to other agents.  

#### The canvas layout

When you open **Agent Orchestration**:

- On the left or top, you will see a **palette** of nodes (agents) you can drag onto the canvas.  
- In the middle, you see the **canvas**, where you build the workflow.  
- On the side, you see a **properties panel** that shows options for the selected node.

**Screenshots:**

- ![Empty agent canvas](documentation_images/screenshot_agent_canvas_empty.png)  
  Suggested content: Empty canvas with the node palette visible.
- ![Example agent workflow](documentation_images/screenshot_agent_canvas_example_flow.png)  
  Suggested content: A simple workflow from Start Node → AI Assistant Agent → End Node.

#### Node types (translated for non‑technical users)

- **Start Node**  
  Where the conversation or workflow begins. Every workflow should have exactly one Start Node.

- **User Proxy Agent**  
  Represents the human user inside the workflow. It can wait for user input or pass messages through to other agents.

- **AI Assistant Agent**  
  The main AI helper that reads context (and optionally documents via DocAware) and produces answers.

- **Group Chat Manager**  
  A coordinator that manages multiple agents. It can:
  - Use **Round Robin Delegation** to cycle through agents in order.  
  - Use **Intelligent Delegation** to choose which agent is best suited for each question.

- **Delegate Agent**  
  A specialist agent that handles a particular type of task (for example, answering questions about pricing, or about a specific product area).

- **End Node**  
  Marks the end of the workflow. Once a path reaches an End Node, that branch of the conversation is done.

#### Building a simple workflow

1. Drag a **Start Node** onto the canvas.  
2. Drag an **AI Assistant Agent** onto the canvas.  
3. Drag an **End Node** onto the canvas.  
4. Connect them in order:
   - Start Node → AI Assistant Agent → End Node.  
5. Click on the **AI Assistant Agent** and open the **properties panel**:
   - Give it a clear name (for example, “Main Assistant”).  
   - Optionally, edit its instructions (system prompt) in simple language.  

![AI Assistant node properties](documentation_images/screenshot_node_properties_ai_assistant.png)  
Suggested content: Properties panel open for an AI Assistant Agent node.

#### Agent configuration (LLM provider and model)

In the properties panel you can set the **LLM provider** (e.g. OpenAI, Anthropic, Google) and **model** (e.g. GPT‑4, Claude) for each agent. This configuration is stored in the workflow: when you save the workflow, the provider and model choices are persisted with it. There is no separate “agent config” store; the workflow graph is the source of truth. Make sure to save the workflow after changing an agent’s provider or model.

---

### Using DocAware in Workflows

**DocAware** allows agents to read and use the documents you uploaded for this project when they answer questions.

#### What DocAware does (plain language)

- Without DocAware, an AI assistant relies mostly on its built‑in general knowledge.  
- With DocAware **enabled**, the assistant:
  - Searches your project documents for relevant sections.  
  - Uses those sections as context when forming answers.  
  - Produces responses that are more grounded in your actual content (for example, policies, manuals, contracts).

DocAware always works **within the current project** only. It never mixes documents from other projects.

#### Enabling DocAware on an agent

1. Go to **Agent Orchestration** and open your workflow.  
2. Click an agent node that supports DocAware, such as:
   - **User Proxy Agent**  
   - **AI Assistant Agent**  
   - (Depending on configuration) **Delegate Agent** or in combination with a Group Chat Manager.  
3. In the properties panel, look for the **DocAware** toggle or switch.  
4. Turn the toggle **On**.  
5. Optionally adjust document search settings, if exposed (for example, how many document snippets to use).

![DocAware toggle in node properties](documentation_images/screenshot_node_properties_docaware_toggle.png)  
Suggested content: Node properties panel with the DocAware toggle clearly highlighted.

#### When should I use DocAware?

- Use DocAware when:
  - You want answers to be strictly based on your own documents.  
  - You are building assistants for internal policies, contracts, or product documentation.  
- You may choose to leave DocAware off if:
  - You are experimenting or testing general conversation flows.  
  - You do not have documents uploaded yet.

#### Example of DocAware’s effect

- Ask: “What is our refund policy for subscription customers?”  
  - **Without DocAware**: The answer may be generic and may not match your real policy.  
  - **With DocAware**: The answer should quote or summarize your actual refund rules from your uploaded documents.

![DocAware before/after effect](documentation_images/screenshot_docaware_effect.png)  
Suggested content: Two example answers to the same question, one before enabling DocAware and one after, annotated in the UI or as callouts.

---

### Running and Testing Workflows

After designing a workflow, you will want to test it interactively.

#### Testing inside the platform

Depending on your configuration, the Agent Orchestration area may offer:

- A **Run** or **Test** button.  
- A **chat panel** where you can:
  - Type questions.  
  - See how the workflow routes messages between agents.  
  - Inspect responses and any visible logs.

Typical testing steps:

1. Ensure your documents are uploaded and processed (if using DocAware).  
2. Open **Agent Orchestration** and select your workflow.  
3. Click the **Run** or **Test** action.  
4. In the chat panel, ask questions relevant to your documents.  
5. Tweak the workflow or agent settings as needed and test again.

![Workflow run and test panel](documentation_images/screenshot_workflow_run_panel.png)  
Suggested content: Workflow run/test panel with a chat conversation showing exchanges between user and AI.

#### Project separation in practice

- If you have **Project A** and **Project B**:
  - Testing a workflow in Project A only uses Project A’s documents and configuration.  
  - Testing a workflow in Project B only uses Project B’s documents and configuration.  

This makes it safe to maintain multiple workflows for different clients or departments at once.

---

### Evaluating Workflows

Evaluation helps you measure how well a workflow performs on a set of test questions.

#### What is evaluation?

In simple terms:

- You prepare a small table (CSV file) with:
  - **Input** – a test question or prompt.  
  - **Expected Output** – the ideal answer in your own words.  
- IntelliDoc runs the workflow on each input and compares the actual answer with your expected answer, producing a **score**.

#### Running an evaluation

1. Go to the **Evaluation** section of your project.  
2. Select the workflow you want to evaluate (if multiple workflows are available).  
3. Upload your evaluation dataset (CSV file).  
4. Start the evaluation.  
5. Wait for the results to be computed.

**Screenshots:**

- ![Evaluation tab empty](documentation_images/screenshot_evaluation_empty.png)  
  Suggested content: Evaluation tab before any dataset is uploaded.

#### Understanding the results

- Each row represents one test question.  
- The system shows:
  - The question (input).  
  - The expected answer.  
  - The actual answer from the workflow.  
  - A similarity score (how close the answers were).  
- Use these results to:
  - Identify where the workflow performs well.  
  - Spot questions where answers are weak or incorrect.  
  - Decide how to improve prompts, workflows, or documents.

Evaluations are defined **per workflow**, and workflows belong to a single project, so each project has its own independent evaluation history.

---

### Deploying a Workflow

Deployment makes a workflow available outside the IntelliDoc console—for example, as a web widget or an API endpoint that other applications can call.

#### What deployment means

- A **deployed workflow** is one that:
  - Has a dedicated endpoint or URL.  
  - Can be called by approved websites or applications.  
  - Is subject to rate limits and access controls.

#### Steps to deploy

1. Go to the **Deploy** section of your project.  
2. If needed, select the workflow you want to deploy.  
3. Configure:
   - **Allowed origin URLs** – which websites are allowed to embed or call this workflow (for example, `https://support.yourcompany.com`).  
   - **Rate limits** – how many requests per minute are allowed from each origin.  
4. Activate the deployment.

**Screenshots:**

- ![Deploy settings](documentation_images/screenshot_deploy_settings.png)  
  Suggested content: Deploy tab with allowed origins and rate limit settings visible.
- ![Deploy active status](documentation_images/screenshot_deploy_active_status.png)  
  Suggested content: Deployment marked as active (for example, with a status tag or toggle).

#### Local vs production deployments

- **Local environment**
  - Useful for internal testing and development.  
  - Origins might be `http://localhost:3000` or similar.  
  - Not intended for external customers.

- **Production environment**
  - Uses your organization’s official domains.  
  - Carefully configure allowed origins to only trusted websites.  
  - Keep rate limits at reasonable levels to protect resources.

---

### Tracking Activity and Conversation History

The **Activity Tracker** section lets you see how deployed workflows are being used over time.

#### Activity list

When you open Activity Tracker, you may see:

- A list of **sessions**, where each session represents a series of messages between a user and your deployed workflow.  
- Basic details such as:
  - Session ID or name.  
  - Time of last activity.  
  - Associated deployment or workflow.

![Activity Tracker list](documentation_images/screenshot_activity_tracker_list.png)  
Suggested content: Activity Tracker list with several example sessions.

#### Viewing conversation details

Click on a session to view:

- The **full conversation history** (questions and answers).  
- Any metadata that is displayed (for example, timestamps).

Use this view to:

- Understand how users interact with your assistant.  
- Identify common questions or failure cases.  
- Decide where to improve documents or workflows.

Each project’s activity is stored separately, so activity in Project A does not appear in Project B.

---

### Working with Multiple Projects Safely

IntelliDoc is designed so that each project is a separate workspace.

#### What is isolated per project?

For each project, the following are **kept separate**:

- Uploaded documents  
- Document processing results (indexes)  
- API keys and model configurations  
- Workflows and deployments  
- Evaluation results  
- Activity and conversation history  

This lets you:

- Serve different customers or departments with their own dedicated AI assistants.  
- Keep confidential documents and conversations isolated.  
- Experiment with new workflows in one project without affecting others.

#### Best practices

- Use clear, descriptive **project names** (for example, “HR Policies – 2026” instead of “Test1”).  
- Create separate projects for:
  - Different business units or regions.  
  - Different stages (for example, “Pilot”, “Production”).  
  - Different clients if you are a service provider.

#### Project separation

Each project operates as an independent pipeline:

- **Project A**: Documents A → Workflows A → Deployment A → Activity A  
- **Project B**: Documents B → Workflows B → Deployment B → Activity B  

Projects never share data or interfere with each other.

---

### Troubleshooting & FAQs

#### Documents not appearing after upload

- Make sure the upload finished successfully (check for any error messages).  
- Refresh the page to see if the document list updates.  
- If the problem persists, contact your administrator with the project name and time of upload.

#### “Start Processing” seems slow

- Large or complex documents can take longer to process.  
- You can continue working in other sections or even in other projects while processing continues.  
- If processing appears stuck for an unusually long time, note the project name and contact support or your admin.

#### The assistant ignores my documents

- Check that:
  - Your documents have been **processed** (not just uploaded).  
  - DocAware is **enabled** on the relevant agent(s) in Agent Orchestration.  
  - You are asking questions that are actually covered by your documents.  

If the problem continues, review the workflow configuration or consult a technical owner.

#### I get errors when trying to deploy or use a deployed workflow

- Verify that:
  - You have added the correct **allowed origin URLs** on the Deploy page.  
  - You are accessing the workflow from one of those origins.  
  - Rate limits are not exceeded (for example, too many requests per minute).  
- If you still see issues, capture any error messages and share them with your administrator.

#### Who should I contact for help?

**Alok Kumar Sahu**  
Senior Research Software Engineer  
AI Competency Centre  
Digital Governance Unit  
University of Oxford  
Email: alok.sahu@it.ox.ac.uk  

#### Get in Touch

For AI consultation and project guidance:  
- Email: aimlcompetencycentre@it.ox.ac.uk  
- Web: oerc.ox.ac.uk/ai-centre  
- Expression of interest: https://bit.ly/contact-aicc

