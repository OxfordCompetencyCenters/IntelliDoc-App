<script lang="ts">
  import { onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';

  interface OllamaModel {
    name: string;
    display_name: string;
    size: string;
    size_formatted?: string;
    family: string;
    description: string;
    downloaded: boolean;
    vision?: boolean;
    parameter_size?: string;
  }

  let ollamaAvailable = false;
  let loading = true;
  let models: OllamaModel[] = [];
  let downloadingModel: string | null = null;
  let downloadProgress = 0;
  let downloadStatus = '';

  onMount(() => {
    loadLibrary();
  });

  async function loadLibrary() {
    try {
      loading = true;
      const resp = await fetch('/api/ollama/library/');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      models = data.models || [];
      ollamaAvailable = data.ollama_available ?? false;

      // Also fetch any extra downloaded models not in curated list
      if (ollamaAvailable) {
        try {
          const localResp = await fetch('/api/ollama/models/');
          const localData = await localResp.json();
          const curatedNames = new Set(models.map(m => m.name));
          for (const lm of (localData.models || [])) {
            if (!curatedNames.has(lm.name)) {
              models = [...models, {
                name: lm.name,
                display_name: lm.name.split(':')[0],
                size: lm.size_formatted || '',
                family: lm.family || '',
                description: 'Custom model',
                downloaded: true,
                vision: false,
                parameter_size: lm.parameter_size || '',
              }];
            }
          }
        } catch {}
      }
    } catch {
      ollamaAvailable = false;
    } finally {
      loading = false;
    }
  }

  async function pullModel(modelName: string) {
    downloadingModel = modelName;
    downloadProgress = 0;
    downloadStatus = 'Starting download...';

    try {
      const resp = await fetch('/api/ollama/pull/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName }),
      });
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.error) throw new Error(data.error);
            downloadStatus = data.status || 'Downloading...';
            if (data.total && data.completed) {
              downloadProgress = Math.round((data.completed / data.total) * 100);
            } else if (data.status === 'success') {
              downloadProgress = 100;
            }
          } catch (e) {
            if (e instanceof SyntaxError) continue;
            throw e;
          }
        }
      }

      toasts.success(`Model "${modelName}" downloaded`);
      models = models.map(m => m.name === modelName ? { ...m, downloaded: true } : m);
    } catch (err: any) {
      toasts.error(`Download failed: ${err.message}`);
    } finally {
      setTimeout(() => {
        downloadingModel = null;
        downloadProgress = 0;
        downloadStatus = '';
      }, 1500);
    }
  }

  async function deleteModel(name: string) {
    if (!confirm(`Delete "${name}"? You can re-download it later.`)) return;
    try {
      await fetch('/api/ollama/delete/', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: name }),
      });
      toasts.success(`Deleted "${name}"`);
      models = models.map(m => m.name === name ? { ...m, downloaded: false } : m);
    } catch (err: any) {
      toasts.error(`Delete failed: ${err.message}`);
    }
  }

  $: downloadedModels = models.filter(m => m.downloaded);
  $: availableModels = models.filter(m => !m.downloaded);
</script>

{#if loading}
  <div class="flex items-center py-3">
    <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
    <span class="text-xs text-gray-500">Checking Ollama...</span>
  </div>
{:else if !ollamaAvailable}
  <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-3">
    <p class="text-sm font-medium text-amber-800">
      <i class="fas fa-exclamation-triangle mr-1"></i> Docker Required
    </p>
    <p class="text-xs text-amber-600 mt-1">
      Install <a href="https://www.docker.com/products/docker-desktop/" target="_blank" class="underline font-medium">Docker Desktop</a> and restart the app to use local AI models.
    </p>
  </div>
{:else}
  <div class="mt-3 space-y-3">
    <!-- Downloaded Models -->
    {#if downloadedModels.length > 0}
      <div>
        <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Downloaded</h4>
        <div class="space-y-1.5">
          {#each downloadedModels as model}
            <div class="flex items-center justify-between bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              <div>
                <div class="flex items-center gap-2">
                  <i class="fas fa-check-circle text-green-500 text-xs"></i>
                  <span class="text-sm font-medium text-gray-800">{model.display_name}</span>
                  {#if model.vision}
                    <span class="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">Vision</span>
                  {/if}
                </div>
                <span class="text-xs text-gray-400 ml-5">{model.size}</span>
              </div>
              <button on:click={() => deleteModel(model.name)}
                class="text-xs text-red-400 hover:text-red-600 px-2 py-1 rounded hover:bg-red-50" title="Delete">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Available Vision Models -->
    {#if availableModels.length > 0}
      <div>
        <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Available Vision Models
        </h4>
        <div class="space-y-1.5">
          {#each availableModels as model}
            <div class="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-gray-700">{model.display_name}</span>
                  <span class="text-xs text-gray-400">{model.size}</span>
                  {#if model.vision}
                    <span class="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">Vision</span>
                  {/if}
                </div>
                <p class="text-xs text-gray-400 truncate">{model.description}</p>
              </div>

              {#if downloadingModel === model.name}
                <div class="ml-3 w-28">
                  <div class="flex justify-between text-xs text-blue-600 mb-1">
                    <span class="truncate text-[10px]">{downloadStatus}</span>
                    <span class="font-mono text-[10px]">{downloadProgress}%</span>
                  </div>
                  <div class="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div class="h-full bg-blue-500 rounded-full transition-all duration-300" style="width: {downloadProgress}%"></div>
                  </div>
                </div>
              {:else}
                <button on:click={() => pullModel(model.name)}
                  disabled={downloadingModel !== null}
                  class="ml-3 text-xs px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap">
                  <i class="fas fa-download mr-1"></i> Download
                </button>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if models.length === 0}
      <p class="text-xs text-gray-400 italic">No vision models available.</p>
    {/if}
  </div>
{/if}
