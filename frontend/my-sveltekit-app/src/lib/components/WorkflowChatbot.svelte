<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { toasts } from '$lib/stores/toast';

  export let projectId: string;
  export let project: any;

  interface Citation {
    ref: number;
    document_title?: string;
    quoted_text?: string;
    page?: string | number;
    section?: string;
    document_id?: string;
    url?: string;
    source?: string;
  }

  interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    elapsed_ms?: number;
    citations?: Citation[];
  }

  interface ChatSession {
    id: string;
    label: string;
    workflow_id: string | null;
    message_count: number;
    preview: string;
    created_at: string;
    updated_at: string;
  }

  interface ActivityItem {
    type: string;
    agent?: string;
    content?: string;
    tool?: string;
    chars?: number;
    tasks?: string[];
  }

  let sessions: ChatSession[] = [];
  let activeSessionId: string | null = null;
  let messages: ChatMessage[] = [];
  let workflows: any[] = [];
  let selectedWorkflowId: string | null = null;
  let messageInput = '';
  let sending = false;
  let loading = true;
  let messagesContainer: HTMLDivElement;
  let renamingId: string | null = null;
  let renameValue = '';
  let fullscreen = false;
  let sidebarOpen = true;

  // Activity panel state
  let activityItems: ActivityItem[] = [];
  let showActivityPanel = false;
  let activityCollapsed = false;
  let activityElapsedText = '';
  let activityStartTime: number | null = null;
  let expandedActivityIdx: number | null = null;

  // Citation tooltip state
  let tooltipCitation: Citation | null = null;
  let tooltipPosition: { left: number; top: number } | null = null;
  let tooltipRef: number | null = null;

  const API = `/api/chatbot/${projectId}`;

  const ACTIVITY_ICONS: Record<string, string> = {
    planning: '\u{1F4CB}', delegate_start: '\u{1F91D}', delegate_plan: '\u{1F4DD}',
    tool_result: '\u{1F50D}', delegate_done: '\u2705', synthesizing: '\u2699\uFE0F',
  };

  onMount(async () => {
    await Promise.all([loadSessions(), loadWorkflows()]);
    loading = false;
  });

  async function loadWorkflows() {
    try {
      const resp = await fetch(`/api/projects/${projectId}/workflows/`);
      if (resp.ok) {
        const data = await resp.json();
        workflows = data.workflows || data || [];
        if (workflows.length > 0 && !selectedWorkflowId)
          selectedWorkflowId = workflows[0].workflow_id || workflows[0].id;
      }
    } catch { workflows = []; }
  }

  async function loadSessions() {
    try {
      const resp = await fetch(`${API}/sessions/`);
      const data = await resp.json();
      sessions = data.sessions || [];
      if (sessions.length > 0 && !activeSessionId) await selectSession(sessions[0].id);
    } catch { sessions = []; }
  }

  async function selectSession(id: string) {
    activeSessionId = id;
    const s = sessions.find(s => s.id === id);
    if (s) selectedWorkflowId = s.workflow_id;
    await loadMessages(id);
  }

  async function loadMessages(sid: string) {
    try {
      const resp = await fetch(`${API}/sessions/${sid}/messages/`);
      const data = await resp.json();
      messages = data.messages || [];
      scrollToBottom();
    } catch { messages = []; }
  }

  async function createSession() {
    if (!selectedWorkflowId) { toasts.error('Select a workflow first'); return; }
    try {
      const resp = await fetch(`${API}/sessions/create/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow_id: selectedWorkflowId, label: `Chat ${sessions.length + 1}` }),
      });
      const data = await resp.json();
      sessions = [{ ...data, preview: '', updated_at: data.created_at }, ...sessions];
      await selectSession(data.id);
    } catch (err: any) { toasts.error(`Failed: ${err.message}`); }
  }

  async function deleteSession(id: string) {
    if (!confirm('Delete this conversation?')) return;
    await fetch(`${API}/sessions/${id}/`, { method: 'DELETE' }).catch(() => {});
    sessions = sessions.filter(s => s.id !== id);
    if (activeSessionId === id) {
      activeSessionId = sessions[0]?.id || null;
      if (activeSessionId) await loadMessages(activeSessionId); else messages = [];
    }
  }

  function startRename(id: string, label: string) { renamingId = id; renameValue = label; }
  async function commitRename() {
    if (!renamingId || !renameValue.trim()) { renamingId = null; return; }
    await fetch(`${API}/sessions/${renamingId}/rename/`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label: renameValue.trim() }),
    }).catch(() => {});
    sessions = sessions.map(s => s.id === renamingId ? { ...s, label: renameValue.trim() } : s);
    renamingId = null;
  }

  async function sendMessage() {
    if (!messageInput.trim() || !activeSessionId || sending) return;
    const text = messageInput.trim();
    messageInput = '';
    sending = true;

    // Reset activity + tooltip state
    activityItems = [];
    showActivityPanel = false;
    activityCollapsed = false;
    activityElapsedText = '';
    activityStartTime = null;
    expandedActivityIdx = null;
    tooltipCitation = null;

    messages = [...messages, { role: 'user', content: text, timestamp: new Date().toISOString() }];
    scrollToBottom();

    // Add placeholder assistant message
    const assistantIdx = messages.length;
    messages = [...messages, { role: 'assistant', content: '', timestamp: new Date().toISOString() }];
    scrollToBottom();

    try {
      const resp = await fetch(`${API}/sessions/${activeSessionId}/send_stream/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      if (!resp.ok || !resp.body) {
        const data = await resp.json();
        messages[assistantIdx] = {
          ...messages[assistantIdx],
          content: data.error ? `Error: ${data.error}` : (data.response || 'No response'),
          elapsed_ms: data.elapsed_ms, citations: data.citations || [],
        };
        messages = [...messages];
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamedContent = '';
      let contentStarted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        while (buffer.includes('\n\n')) {
          const eventEnd = buffer.indexOf('\n\n');
          const eventBlock = buffer.slice(0, eventEnd);
          buffer = buffer.slice(eventEnd + 2);

          let eventType = '';
          let eventData = '';
          for (const line of eventBlock.split('\n')) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim();
            else if (line.startsWith('data: ')) eventData = line.slice(6);
          }
          if (!eventData) continue;

          try {
            const data = JSON.parse(eventData);

            // Intermediate events → activity panel
            if (['planning', 'delegate_start', 'delegate_plan', 'tool_result', 'delegate_done', 'synthesizing'].includes(eventType)) {
              if (!showActivityPanel) {
                showActivityPanel = true;
                activityStartTime = Date.now();
              }
              activityItems = [...activityItems, { type: eventType, ...data }];
              scrollToBottom();

            // Content streaming (word-by-word or real Ollama chunks)
            } else if (eventType === 'content' || eventType === 'chunk') {
              if (!contentStarted) {
                contentStarted = true;
                // Collapse activity panel when content starts
                if (showActivityPanel) {
                  const elapsed = activityStartTime ? Math.round((Date.now() - activityStartTime) / 1000) : 0;
                  activityElapsedText = `Processed in ${elapsed}s \u2014 click to expand`;
                  activityCollapsed = true;
                }
              }
              streamedContent += data.content || '';
              messages[assistantIdx] = { ...messages[assistantIdx], content: streamedContent };
              messages = [...messages];
              scrollToBottom();

            // Citations as separate event
            } else if (eventType === 'citations') {
              if (Array.isArray(data.citations) && data.citations.length > 0) {
                messages[assistantIdx] = { ...messages[assistantIdx], citations: data.citations };
                messages = [...messages];
              }

            // Done — finalize
            } else if (eventType === 'done') {
              if (showActivityPanel && !activityCollapsed) {
                const elapsed = activityStartTime ? Math.round((Date.now() - activityStartTime) / 1000) : 0;
                activityElapsedText = `Processed in ${elapsed}s \u2014 click to expand`;
                activityCollapsed = true;
              }
              messages[assistantIdx] = {
                ...messages[assistantIdx],
                content: data.response || streamedContent,
                elapsed_ms: data.elapsed_ms,
                citations: data.citations || messages[assistantIdx].citations || [],
              };
              messages = [...messages];
              sessions = sessions.map(s => {
                if (s.id !== activeSessionId) return s;
                const isFirstMessage = s.message_count === 0 || s.label.startsWith('Chat ');
                return {
                  ...s,
                  label: isFirstMessage ? text.slice(0, 50) : s.label,
                  preview: '',
                  message_count: data.message_count || s.message_count + 1,
                  updated_at: new Date().toISOString(),
                };
              });

            } else if (eventType === 'error') {
              messages[assistantIdx] = { ...messages[assistantIdx], content: `Error: ${data.error}` };
              messages = [...messages];
            }
          } catch { /* skip malformed JSON */ }
        }
      }
    } catch (err: any) {
      messages[assistantIdx] = { ...messages[assistantIdx], content: `Error: ${err.message}` };
      messages = [...messages];
    } finally {
      sending = false;
      scrollToBottom();
    }
  }

  function scrollToBottom() {
    setTimeout(() => { if (messagesContainer) messagesContainer.scrollTop = messagesContainer.scrollHeight; }, 50);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    if (e.key === 'Escape') {
      if (tooltipCitation) { tooltipCitation = null; return; }
      if (fullscreen) { fullscreen = false; }
    }
    if (e.key === 'f' && !sending && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
      fullscreen = !fullscreen;
    }
  }

  // Citation tooltip handling
  function handleCitationClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    const chip = target.closest('.cite-chip') as HTMLElement | null;
    if (chip && chip.dataset.ref) {
      e.stopPropagation();
      const refNum = parseInt(chip.dataset.ref);
      // Toggle if same chip
      if (tooltipRef === refNum && tooltipCitation) {
        tooltipCitation = null; tooltipRef = null; tooltipPosition = null;
        return;
      }
      // Find citation from messages
      const allCitations: Citation[] = [];
      for (const msg of [...messages].reverse()) {
        if (msg.role === 'assistant' && msg.citations?.length) allCitations.push(...msg.citations);
      }
      const cite = allCitations.find(c => c.ref === refNum);
      if (cite) {
        const rect = chip.getBoundingClientRect();
        tooltipPosition = { left: Math.min(rect.left, window.innerWidth - 360), top: rect.bottom + 6 };
        tooltipCitation = cite;
        tooltipRef = refNum;
      }
    } else if (!target.closest('.cite-tooltip')) {
      tooltipCitation = null; tooltipRef = null; tooltipPosition = null;
    }
  }

  function openCitationDocument(documentId: string | undefined) {
    if (!projectId || !documentId) return;
    fetch(`/api/projects/${projectId}/documents/${documentId}/download/`)
      .then(resp => { if (!resp.ok) throw new Error('HTTP ' + resp.status); return resp.blob(); })
      .then(blob => {
        const blobUrl = URL.createObjectURL(blob);
        window.open(blobUrl, '_blank');
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
      })
      .catch(err => console.error('Citation doc open failed:', err));
  }

  function getActivityDesc(item: ActivityItem): string {
    switch (item.type) {
      case 'planning': return `<b>${item.agent || ''}</b> created a plan`;
      case 'delegate_start': return `<b>${item.agent || ''}</b> started \u2014 ${Array.isArray(item.tasks) ? item.tasks.length + ' task(s)' : ''}`;
      case 'delegate_plan': return `<b>${item.agent || ''}</b> created its plan`;
      case 'tool_result': return `<b>${item.agent || ''}</b> queried <i>${item.tool || ''}</i> (${item.chars || 0} chars)`;
      case 'delegate_done': return `<b>${item.agent || ''}</b> finished (${item.chars || 0} chars)`;
      case 'synthesizing': return `<b>${item.agent || ''}</b> is synthesizing the final answer`;
      default: return item.type;
    }
  }

  function getActivityDetail(item: ActivityItem): string {
    if ((item.type === 'planning' || item.type === 'delegate_plan') && item.content) return item.content;
    if (item.type === 'delegate_start' && Array.isArray(item.tasks) && item.tasks.length)
      return item.tasks.map((t, i) => `${i + 1}. ${t}`).join('\n');
    if (item.type === 'tool_result' && item.content) return item.content;
    return '';
  }

  function renderMarkdown(text: string): string {
    if (!text) return '';
    // Safety: strip ---CITATIONS--- block and all citation JSON that follows
    text = text.replace(/---\s*CITATIONS\s*---[\s\S]*?---\s*END_?CITATIONS\s*---/g, '');
    // Strip ---CITATIONS--- without END marker (catches partial blocks during streaming)
    text = text.replace(/---\s*CITATIONS\s*---\s*\[[\s\S]*$/g, '');
    // Strip trailing CITATIONS header and --- separators
    text = text.replace(/[\n\r]+[-*#\s]*CITATIONS[-*#\s]*\s*$/i, '');
    text = text.replace(/\n---+\s*$/g, '').trim();

    let html = text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="chat-code"><code>$2</code></pre>')
      .replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>')
      .replace(/^#{3}\s*(.+?)$/gm, '<h4 class="chat-h">$1</h4>')
      .replace(/^#{2}\s*(.+?)$/gm, '<h4 class="chat-h">$1</h4>')
      .replace(/^#{1}\s*(.+?)$/gm, '<h4 class="chat-h">$1</h4>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(?<!^|\n)\*([^*\n]+)\*/g, '<em>$1</em>')
      // Citation chips: [N] → superscript colored chip
      .replace(/\[(\d+)\]/g, '<span class="cite-chip" data-ref="$1">$1</span>')
      .replace(/\[(\d+(?:,\s*\d+)+)\]/g, (_match: string, nums: string) =>
        nums.split(',').map((n: string) => `<span class="cite-chip" data-ref="${n.trim()}">${n.trim()}</span>`).join(''))
      .replace(/^[\*\-]\s+(.+)$/gm, '<li>$1</li>')
      .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
      .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul class="chat-list">$1</ul>');

    // ── Table rendering ──
    // Detect markdown tables (lines starting with |) and convert to <table>
    const lines = html.split('\n');
    const processed: string[] = [];
    let tableRows: string[] = [];

    function flushTable() {
      if (tableRows.length === 0) return;
      let thtml = '<table class="chat-table">';
      let isFirst = true;
      for (const row of tableRows) {
        // Skip separator rows (| --- | --- | or | :--- | :--- |)
        if (/^\|[\s\-:]+\|/.test(row) && !/[a-zA-Z0-9]/.test(row.replace(/[\|\-:\s]/g, ''))) continue;
        const cells = row.split('|').filter((_, i, a) => i > 0 && i < a.length - 1).map(c => c.trim());
        if (cells.length === 0) continue;
        const tag = isFirst ? 'th' : 'td';
        thtml += '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
        if (isFirst) isFirst = false;
      }
      thtml += '</table>';
      processed.push(thtml);
      tableRows = [];
    }

    for (const line of lines) {
      if (line.trimStart().startsWith('|') && line.trimEnd().endsWith('|')) {
        tableRows.push(line);
      } else {
        flushTable();
        processed.push(line);
      }
    }
    flushTable();
    html = processed.join('\n');

    html = html.replace(/\n/g, '<br>');
    html = html.replace(/<\/(h4|ul|pre|li|table)><br>/g, '</$1>').replace(/<br><(h4|ul|pre|table)/g, '<$1');
    return html;
  }

  function formatTime(iso: string) {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  function formatDate(iso: string) {
    const d = new Date(iso); const now = new Date();
    return d.toDateString() === now.toDateString() ? formatTime(iso) : d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="{fullscreen ? 'fixed inset-0 z-[9999]' : ''} flex flex-col"
  style="height: {fullscreen ? '100vh' : 'calc(100vh - 260px)'}; min-height: 400px;">
  <!-- Top bar -->
  <div style="background-color: #002147;" class="flex items-center justify-between px-3 py-2 shrink-0">
    <div class="flex items-center gap-3">
      <select bind:value={selectedWorkflowId}
        style="background: rgba(255,255,255,0.1); color: white; border-color: rgba(255,255,255,0.2);"
        class="text-xs px-2 py-1 rounded-md border focus:outline-none focus:ring-1 focus:ring-white/30">
        <option value={null} style="color: black;">Select workflow...</option>
        {#each workflows as wf}
          <option value={wf.workflow_id || wf.id} style="color: black;">{wf.name || 'Workflow'}</option>
        {/each}
      </select>
      <button on:click={createSession} disabled={!selectedWorkflowId}
        style="color: white; opacity: {selectedWorkflowId ? 1 : 0.4};"
        class="text-xs px-3 py-1 rounded-md border border-white/20 hover:bg-white/10 disabled:cursor-not-allowed transition-colors">
        <i class="fas fa-plus mr-1"></i> New Chat
      </button>
      <button on:click={() => sidebarOpen = !sidebarOpen}
        style="color: rgba(255,255,255,0.6);" class="text-xs px-2 py-1 hover:text-white">
        <i class="fas {sidebarOpen ? 'fa-angle-double-left' : 'fa-angle-double-right'}"></i>
      </button>
    </div>
    <div class="flex items-center gap-2">
      <span style="color: rgba(255,255,255,0.3);" class="text-[10px]">Press F for fullscreen</span>
      <button on:click={() => fullscreen = !fullscreen}
        style="color: rgba(255,255,255,0.6);" class="text-sm px-2 py-1 rounded hover:bg-white/10 hover:text-white">
        <i class="fas {fullscreen ? 'fa-compress' : 'fa-expand'}"></i>
      </button>
    </div>
  </div>

  <!-- Main body -->
  <div class="flex flex-1 min-h-0 bg-white">
    <!-- Sidebar -->
    {#if sidebarOpen}
      <div class="w-56 bg-gray-50 border-r border-gray-200 flex flex-col shrink-0 overflow-hidden">
        <div class="flex-1 overflow-y-auto">
          {#each sessions as session (session.id)}
            <div
              class="px-3 py-2 border-b border-gray-100 cursor-pointer transition-all
                {activeSessionId === session.id ? 'bg-blue-50 border-l-2 border-l-blue-600' : 'hover:bg-gray-100 border-l-2 border-l-transparent'}"
              on:click={() => selectSession(session.id)}
              on:keydown={(e) => e.key === 'Enter' && selectSession(session.id)}
              role="button" tabindex="0">
              {#if renamingId === session.id}
                <input bind:value={renameValue} on:blur={commitRename}
                  on:keydown={(e) => e.key === 'Enter' && commitRename()}
                  class="w-full text-xs px-1.5 py-0.5 border border-blue-400 rounded" autofocus />
              {:else}
                <div class="flex items-center justify-between">
                  <div class="min-w-0 flex-1">
                    <div class="text-xs font-medium text-gray-800 truncate leading-snug">{session.label}</div>
                    <div class="text-[10px] text-gray-300 mt-0.5">{formatDate(session.updated_at || session.created_at)}</div>
                  </div>
                  {#if activeSessionId === session.id}
                    <div class="flex gap-0.5 shrink-0 ml-1">
                      <button on:click|stopPropagation={() => startRename(session.id, session.label)}
                        class="text-gray-400 hover:text-blue-500 p-0.5"><i class="fas fa-pen text-[9px]"></i></button>
                      <button on:click|stopPropagation={() => deleteSession(session.id)}
                        class="text-gray-400 hover:text-red-500 p-0.5"><i class="fas fa-trash text-[9px]"></i></button>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
          {#if sessions.length === 0 && !loading}
            <div class="p-4 text-center text-xs text-gray-400">
              <i class="fas fa-comments text-gray-300 text-xl mb-2 block"></i>
              Select a workflow and click "New Chat"
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Chat area -->
    <div class="flex-1 flex flex-col min-w-0">
      <div bind:this={messagesContainer} on:click={handleCitationClick}
        class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {#if messages.length === 0}
          <div class="flex items-center justify-center h-full">
            <div class="text-center">
              <div class="w-14 h-14 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <i class="fas fa-comments text-gray-300 text-xl"></i>
              </div>
              <p class="text-sm text-gray-500 font-medium">
                {activeSessionId ? 'Send a message to start' : 'Create a conversation to begin'}
              </p>
            </div>
          </div>
        {/if}

        {#each messages as msg, msgIdx}
          <!-- Activity Panel: show BEFORE the last assistant message (streaming placeholder) -->
          {#if showActivityPanel && msg.role === 'assistant' && msgIdx === messages.length - 1}
            <div class="activity-panel" class:collapsed={activityCollapsed}>
              <div class="activity-header" on:click={() => activityCollapsed = !activityCollapsed}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
                <span>{activityCollapsed ? activityElapsedText || 'Processed' : 'Processing\u2026'}</span>
              </div>
              {#if !activityCollapsed}
                <div class="activity-items">
                  {#each activityItems as item, idx}
                    {@const detail = getActivityDetail(item)}
                    <div class="activity-item"
                      class:expandable={!!detail}
                      class:expanded={expandedActivityIdx === idx}
                      on:click={() => { if (detail) expandedActivityIdx = expandedActivityIdx === idx ? null : idx; }}>
                      <span class="activity-item-icon">{ACTIVITY_ICONS[item.type] || '\u2022'}</span>
                      <span class="activity-item-body">
                        {@html getActivityDesc(item)}
                        {#if detail && expandedActivityIdx === idx}
                          <div class="activity-detail">{detail}</div>
                        {/if}
                      </span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          <div class="flex {msg.role === 'user' ? 'justify-end' : 'justify-start'}">
            <div class="max-w-[75%] {msg.role === 'user'
              ? 'rounded-2xl rounded-br-sm px-4 py-2.5 shadow-sm'
              : 'bg-gray-50 border border-gray-200 text-gray-800 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm'}"
              style="{msg.role === 'user' ? 'background-color: #002147;' : ''}">
              {#if msg.role === 'user'}
                <div class="text-sm whitespace-pre-wrap leading-relaxed" style="color: white;">{msg.content}</div>
              {:else}
                <div class="text-sm leading-relaxed text-gray-800 chat-markdown">{@html renderMarkdown(msg.content)}</div>
              {/if}
              <div class="flex items-center justify-end gap-2 mt-1">
                <span class="text-[10px]" style="color: {msg.role === 'user' ? 'rgba(191,219,254,0.9)' : '#9ca3af'}">
                  {formatTime(msg.timestamp)}
                </span>
                {#if msg.elapsed_ms}
                  <span class="text-[10px]" style="color: {msg.role === 'user' ? 'rgba(191,219,254,0.9)' : '#9ca3af'}">
                    {(msg.elapsed_ms / 1000).toFixed(1)}s
                  </span>
                {/if}
              </div>
            </div>
          </div>
        {/each}

        <!-- Thinking indicator (only when no content yet and no activity panel) -->
        {#if sending && !messages[messages.length - 1]?.content && !showActivityPanel}
          <div class="flex justify-start">
            <div class="bg-gray-50 border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
              <div class="flex items-center gap-2">
                <div class="flex gap-1">
                  <div class="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                  <div class="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                  <div class="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
                </div>
                <span class="text-xs text-gray-500">Processing...</span>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Input -->
      <div class="px-3 py-2 border-t border-gray-200 bg-white">
        <div class="flex gap-2 items-end">
          <textarea bind:value={messageInput} on:keydown={handleKeydown}
            placeholder={activeSessionId ? 'Type a message... (Enter to send)' : 'Create a chat first'}
            disabled={!activeSessionId || sending} rows="1"
            class="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-xl resize-none focus:border-gray-500 focus:ring-1 focus:ring-gray-500/20 disabled:bg-gray-50 disabled:text-gray-400 max-h-28"
            style="min-height: 38px;"></textarea>
          <button on:click={sendMessage} disabled={!activeSessionId || !messageInput.trim() || sending}
            style="background-color: #002147;" class="px-3 py-2 text-white rounded-xl hover:opacity-90 disabled:opacity-30 disabled:cursor-not-allowed transition-opacity shrink-0">
            {#if sending}<i class="fas fa-spinner fa-spin text-sm"></i>{:else}<i class="fas fa-paper-plane text-sm"></i>{/if}
          </button>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Citation Tooltip -->
{#if tooltipCitation && tooltipPosition}
  <div class="cite-tooltip"
    style="left: {tooltipPosition.left}px; top: {tooltipPosition.top}px;"
    on:click|stopPropagation>
    <div class="cite-tooltip-title">
      {#if tooltipCitation.document_id}
        <a class="cite-tooltip-link" href="#"
          on:click|preventDefault={() => openCitationDocument(tooltipCitation?.document_id)}>
          {tooltipCitation.document_title || 'Document'}
          {#if tooltipCitation.page || tooltipCitation.section}
            &mdash; {tooltipCitation.page ? `p.${tooltipCitation.page}` : ''}{tooltipCitation.section ? `, ${tooltipCitation.section}` : ''}
          {/if}
        </a>
      {:else if tooltipCitation.url}
        <a class="cite-tooltip-link" href={tooltipCitation.url} target="_blank" rel="noopener">
          {tooltipCitation.document_title || tooltipCitation.url}
        </a>
      {:else}
        {tooltipCitation.document_title || 'Source'}
      {/if}
    </div>
    {#if tooltipCitation.quoted_text}
      <div class="cite-tooltip-quote">
        &ldquo;{tooltipCitation.quoted_text.slice(0, 300)}&rdquo;
      </div>
    {/if}
  </div>
{/if}

<style>
  /* ── Markdown ───────────────────────────────────────────── */
  :global(.chat-markdown h4.chat-h) { font-size: 0.95rem; font-weight: 700; margin: 0.6rem 0 0.3rem; color: #1e293b; }
  :global(.chat-markdown ul.chat-list) { list-style: disc; padding-left: 1.25rem; margin: 0.3rem 0; }
  :global(.chat-markdown ul.chat-list li) { margin-bottom: 0.2rem; }
  :global(.chat-markdown strong) { font-weight: 600; color: #0f172a; }
  :global(.chat-markdown pre.chat-code) {
    background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 0.5rem 0.75rem; overflow-x: auto; font-size: 0.8rem; margin: 0.4rem 0;
  }
  :global(.chat-markdown code.chat-inline-code) { background: #f1f5f9; border-radius: 3px; padding: 1px 4px; font-size: 0.85em; }

  /* ── Tables ─────────────────────────────────────────────── */
  :global(.chat-markdown .chat-table) {
    width: 100%; border-collapse: collapse; margin: 0.5rem 0; font-size: 0.8rem;
  }
  :global(.chat-markdown .chat-table th) {
    background: #f1f5f9; font-weight: 600; color: #1e293b;
    padding: 6px 10px; border: 1px solid #e2e8f0; text-align: left;
  }
  :global(.chat-markdown .chat-table td) {
    padding: 5px 10px; border: 1px solid #e2e8f0; color: #475569;
  }
  :global(.chat-markdown .chat-table tr:nth-child(even) td) {
    background: #f8fafc;
  }

  /* ── Citation Chips ─────────────────────────────────────── */
  :global(.cite-chip) {
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    min-width: 18px !important; height: 18px !important; padding: 0 5px !important;
    border-radius: 9px !important; background: #2563eb !important; color: #ffffff !important;
    font-size: 10px !important; font-weight: 700 !important; cursor: pointer !important;
    vertical-align: super !important; margin: 0 2px !important; line-height: 1 !important;
    transition: all 0.15s !important; box-shadow: 0 1px 2px rgba(37,99,235,0.3) !important;
    text-decoration: none !important; -webkit-text-fill-color: #ffffff !important;
  }
  :global(.cite-chip:hover) { background: #1d4ed8 !important; transform: scale(1.12); box-shadow: 0 2px 6px rgba(37,99,235,0.4) !important; }
  :global(.cite-chip-secondary) { background: #e5e7eb; color: #374151; cursor: default; }
  :global(.cite-chip-secondary:hover) { filter: none; }

  /* ── Citation Tooltip ───────────────────────────────────── */
  .cite-tooltip {
    position: fixed; max-width: 360px;
    background: #1e293b !important; color: #e2e8f0 !important;
    border-radius: 10px; padding: 12px 16px;
    font-size: 13px; box-shadow: 0 8px 30px rgba(0,0,0,0.4);
    z-index: 10001; animation: citeIn 0.15s ease-out;
    border: 1px solid rgba(255,255,255,0.1);
  }
  .cite-tooltip-title { font-weight: 600; color: #7dd3fc !important; margin-bottom: 8px; font-size: 13px; }
  .cite-tooltip-link {
    color: #7dd3fc !important; text-decoration: underline; text-underline-offset: 2px;
    cursor: pointer; transition: color 0.15s;
  }
  .cite-tooltip-link:hover { color: #bae6fd !important; }
  .cite-tooltip-quote {
    font-style: italic; color: #cbd5e1 !important; font-size: 12px; line-height: 1.5;
    -webkit-text-fill-color: #cbd5e1 !important;
  }
  @keyframes citeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* ── Activity Panel ─────────────────────────────────────── */
  .activity-panel {
    background: #f1f5f9; border: 1px solid #e2e8f0;
    border-radius: 12px; margin: 4px 0;
    overflow: hidden; transition: max-height 0.35s ease, opacity 0.25s ease;
    max-height: 320px; opacity: 1;
  }
  .activity-panel.collapsed { max-height: 32px; cursor: pointer; }
  .activity-header {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 12px; font-size: 12px; font-weight: 600;
    color: #64748b; user-select: none; cursor: pointer;
  }
  .activity-header svg {
    width: 14px; height: 14px; flex-shrink: 0;
    transition: transform 0.25s;
  }
  .activity-panel.collapsed .activity-header svg { transform: rotate(-90deg); }
  .activity-items { max-height: 260px; overflow-y: auto; padding: 0 12px 8px; }
  .activity-panel.collapsed .activity-items { display: none; }
  .activity-item {
    display: flex; align-items: flex-start; gap: 8px;
    padding: 5px 0; font-size: 12px; color: #475569;
    line-height: 1.45; border-bottom: 1px solid #e2e8f0;
    animation: actItemIn 0.2s ease-out;
  }
  .activity-item:last-child { border-bottom: none; }
  .activity-item-icon {
    flex-shrink: 0; width: 18px; height: 18px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 4px; font-size: 11px;
  }
  :global(.activity-item-body b) { color: #334155; }
  .activity-item.expandable { cursor: pointer; flex-wrap: wrap; }
  .activity-item.expandable:hover { background: #e2e8f0; border-radius: 6px; }
  :global(.activity-item.expandable .activity-item-body::after) {
    content: ' \25B8'; font-size: 10px; color: #94a3b8; transition: transform 0.2s;
  }
  :global(.activity-item.expanded .activity-item-body::after) { content: ' \25BE'; }
  .activity-detail {
    width: 100%; margin-top: 4px; padding: 8px 10px;
    background: #e8ecf1; border-radius: 6px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px; line-height: 1.55; color: #334155;
    white-space: pre-wrap; word-break: break-word;
    max-height: 180px; overflow-y: auto;
    animation: detailSlide 0.2s ease-out;
  }
  @keyframes actItemIn {
    from { opacity: 0; transform: translateX(-8px); }
    to { opacity: 1; transform: translateX(0); }
  }
  @keyframes detailSlide {
    from { opacity: 0; max-height: 0; }
    to { opacity: 1; max-height: 180px; }
  }
</style>
