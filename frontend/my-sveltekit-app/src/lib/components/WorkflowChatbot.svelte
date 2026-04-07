<script lang="ts">
  import { onMount } from 'svelte';
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
  let activeCitation: Citation | null = null;
  let sidebarOpen = true;

  const API = `/api/chatbot/${projectId}`;

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
    messages = [...messages, { role: 'user', content: text, timestamp: new Date().toISOString() }];
    scrollToBottom();
    try {
      const resp = await fetch(`${API}/sessions/${activeSessionId}/send/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await resp.json();
      if (data.error) {
        messages = [...messages, { role: 'assistant', content: `Error: ${data.error}`, timestamp: new Date().toISOString() }];
      } else {
        messages = [...messages, { role: 'assistant', content: data.response || 'No response',
          timestamp: new Date().toISOString(), elapsed_ms: data.elapsed_ms, citations: data.citations || [] }];
      }
      // Update session — use first message as label (instead of "Chat N")
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
    } catch (err: any) {
      messages = [...messages, { role: 'assistant', content: `Error: ${err.message}`, timestamp: new Date().toISOString() }];
    } finally { sending = false; scrollToBottom(); }
  }

  function scrollToBottom() {
    setTimeout(() => { if (messagesContainer) messagesContainer.scrollTop = messagesContainer.scrollHeight; }, 50);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    if (e.key === 'Escape' && fullscreen) { fullscreen = false; }
    if (e.key === 'f' && !sending && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
      fullscreen = !fullscreen;
    }
  }

  function handleCitationClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (target.classList.contains('chat-cite') && target.dataset.ref) {
      const refNum = parseInt(target.dataset.ref);
      const allCitations: Citation[] = [];
      for (const msg of [...messages].reverse()) {
        if (msg.role === 'assistant' && msg.citations?.length) allCitations.push(...msg.citations);
      }
      const cite = allCitations.find(c => c.ref === refNum);
      activeCitation = cite || { ref: refNum, document_title: `Source [${refNum}]`,
        quoted_text: 'Citation details not available for this message. Send a new question to get source details.' };
    }
  }

  function renderMarkdown(text: string): string {
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="chat-code"><code>$2</code></pre>')
      .replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>')
      .replace(/^#{3}\s*(.+?)$/gm, '<h4 class="chat-h">$1</h4>')
      .replace(/^#{2}\s*(.+?)$/gm, '<h4 class="chat-h">$1</h4>')
      .replace(/^#{1}\s*(.+?)$/gm, '<h4 class="chat-h">$1</h4>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(?<!^|\n)\*([^*\n]+)\*/g, '<em>$1</em>')
      .replace(/\[(\d+)\]/g, '<button class="chat-cite" data-ref="$1" title="View source">[$1]</button>')
      .replace(/\[(\d+(?:,\s*\d+)+)\]/g, (match, nums) =>
        nums.split(',').map((n: string) => `<button class="chat-cite" data-ref="${n.trim()}" title="View source">[${n.trim()}]</button>`).join(''))
      .replace(/^[\*\-]\s+(.+)$/gm, '<li>$1</li>')
      .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
      .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul class="chat-list">$1</ul>')
      .replace(/\n/g, '<br>');
    html = html.replace(/<\/(h4|ul|pre|li)><br>/g, '</$1>').replace(/<br><(h4|ul|pre)/g, '<$1');
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
  style="height: {fullscreen ? '100vh' : 'calc(100vh - 220px)'}; min-height: 400px;">
  <!-- Top bar: workflow selector + controls -->
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

        {#each messages as msg}
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

        {#if sending}
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

<!-- Citation Modal -->
{#if activeCitation}
  <div class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/30" on:click={() => activeCitation = null}>
    <div class="bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden" on:click|stopPropagation>
      <div style="background-color: #002147;" class="px-5 py-3 flex items-center justify-between">
        <h3 style="color: white;" class="font-semibold text-sm flex items-center gap-2">
          <span style="background: rgba(255,255,255,0.2); color: white;" class="rounded px-2 py-0.5 text-xs">[{activeCitation.ref}]</span>
          {activeCitation.document_title || 'Document'}
        </h3>
        <button on:click={() => activeCitation = null} style="color: rgba(255,255,255,0.7);" class="hover:text-white text-lg">
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="p-5 max-h-80 overflow-y-auto">
        {#if activeCitation.quoted_text}
          <div class="mb-3">
            <div class="text-xs font-medium text-gray-500 uppercase mb-1">Quoted Passage</div>
            <blockquote class="text-sm text-gray-700 border-l-4 border-blue-400 pl-3 italic bg-blue-50 rounded-r-lg p-3">
              "{activeCitation.quoted_text}"
            </blockquote>
          </div>
        {/if}
        {#if activeCitation.page || activeCitation.section}
          <div class="flex gap-4 text-xs text-gray-500">
            {#if activeCitation.page}<span><i class="fas fa-file-alt mr-1"></i> Page {activeCitation.page}</span>{/if}
            {#if activeCitation.section}<span><i class="fas fa-bookmark mr-1"></i> {activeCitation.section}</span>{/if}
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  :global(.chat-markdown h4.chat-h) { font-size: 0.95rem; font-weight: 700; margin: 0.6rem 0 0.3rem; color: #1e293b; }
  :global(.chat-markdown ul.chat-list) { list-style: disc; padding-left: 1.25rem; margin: 0.3rem 0; }
  :global(.chat-markdown ul.chat-list li) { margin-bottom: 0.2rem; }
  :global(.chat-markdown strong) { font-weight: 600; color: #0f172a; }
  :global(.chat-markdown .chat-cite) {
    display: inline-block; font-size: 0.65rem; font-weight: 600; color: #2563eb;
    background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px;
    padding: 0 4px; margin: 0 1px; vertical-align: super; line-height: 1;
    cursor: pointer; transition: all 0.15s;
  }
  :global(.chat-markdown .chat-cite:hover) {
    background: #dbeafe; border-color: #93c5fd; transform: scale(1.1);
    box-shadow: 0 1px 3px rgba(37,99,235,0.2);
  }
  :global(.chat-markdown pre.chat-code) {
    background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 0.5rem 0.75rem; overflow-x: auto; font-size: 0.8rem; margin: 0.4rem 0;
  }
  :global(.chat-markdown code.chat-inline-code) { background: #f1f5f9; border-radius: 3px; padding: 1px 4px; font-size: 0.85em; }
</style>
