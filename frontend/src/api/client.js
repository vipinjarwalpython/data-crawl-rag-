/**
 * CrawlRAG API Client
 * Connects the React frontend with the FastAPI backend.
 */

const API_BASE_URL = ''; // Proxied via Vite config to http://127.0.0.1:8000

export async function checkBackendHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return { healthy: false, error: 'Status not OK' };
    const data = await response.json();
    return { healthy: data.status === 'healthy', data };
  } catch (error) {
    return { healthy: false, error: error.message };
  }
}

export async function fetchPipelineStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/rag/status`);
    if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to fetch status`);
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch pipeline status:', error);
    return null;
  }
}

export async function startWebsiteCrawl(options) {
  const payload = {
    url: options.url,
    max_depth: Number(options.maxDepth || 2),
    max_pages: Number(options.maxPages || 25),
    render_js: Boolean(options.renderJs ?? true),
    wait_seconds: 2.0,
    concurrency: 3,
    delay_seconds: 0.5,
    force_refresh: Boolean(options.forceRefresh || false),
  };

  const response = await fetch(`${API_BASE_URL}/api/v1/scraping/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Scraping failed' }));
    throw new Error(err.detail || `Scraping failed with status ${response.status}`);
  }

  return await response.json();
}

export async function buildRagIndex(batchSize = 32) {
  const response = await fetch(`${API_BASE_URL}/api/v1/rag/embed-all`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ batch_size: batchSize }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Embedding failed' }));
    throw new Error(err.detail || `Embedding failed with status ${response.status}`);
  }

  return await response.json();
}

export async function askRagChatbot(query, options = {}) {
  const payload = {
    query: query.trim(),
    top_k: options.topK || 7,
    score_threshold: options.scoreThreshold ?? 0.2,
    reframe: options.reframe ?? true,
    temperature: options.temperature ?? 0.1,
    max_new_tokens: options.maxNewTokens ?? 512,
  };

  const response = await fetch(`${API_BASE_URL}/api/v1/rag/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Answer generation failed' }));
    throw new Error(err.detail || `Answer generation failed with status ${response.status}`);
  }

  return await response.json();
}
