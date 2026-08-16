import React, { useState } from 'react';
import { Settings, Play, RefreshCw, ChevronDown, ChevronUp, CheckCircle2, Globe2 } from 'lucide-react';
import { Icon3DCrawler, Icon3DDatabase, Icon3DSparkles } from './Icons3D';
import PipelineStepper from './PipelineStepper';

export default function Sidebar({
  pipelineStatus,
  onRefreshStatus,
  isIngesting,
  currentStep,
  ingestError,
  onStartIngest,
}) {
  const [url, setUrl] = useState('https://books.toscrape.com/');
  const [maxDepth, setMaxDepth] = useState(1);
  const [maxPages, setMaxPages] = useState(15);
  const [renderJs, setRenderJs] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const presets = [
    { label: 'Books Store (50+ items)', url: 'https://books.toscrape.com/' },
    { label: 'Quotes Catalog', url: 'https://quotes.toscrape.com/' },
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    onStartIngest({
      url: url.trim(),
      maxDepth,
      maxPages,
      renderJs,
    });
  };

  return (
    <aside className="sidebar">
      {/* Card 1: Ingest Website */}
      <div className="card-3d">
        <div className="card-title">
          <Icon3DCrawler size={28} glow={true} />
          <span>Ingest & Index Target</span>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="target-url">
              Website URL to Crawl
            </label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <input
                id="target-url"
                type="url"
                required
                className="input-text"
                placeholder="https://example.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={isIngesting}
                style={{ paddingLeft: 34 }}
              />
              <Globe2
                size={16}
                color="#818cf8"
                style={{ position: 'absolute', left: 10, pointerEvents: 'none' }}
              />
            </div>

            <div className="preset-chips">
              {presets.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  className="chip-btn"
                  onClick={() => setUrl(preset.url)}
                  disabled={isIngesting}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* Collapsible Advanced Settings */}
          <div style={{ marginBottom: 14 }}>
            <button
              type="button"
              className="settings-toggle"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Settings size={13} color="#94a3b8" />
                <span>Crawl Configuration</span>
              </span>
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {showAdvanced && (
              <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label">Max Depth</label>
                    <input
                      type="number"
                      min={0}
                      max={5}
                      className="input-text"
                      value={maxDepth}
                      onChange={(e) => setMaxDepth(Number(e.target.value))}
                      disabled={isIngesting}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Max Pages</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      className="input-text"
                      value={maxPages}
                      onChange={(e) => setMaxPages(Number(e.target.value))}
                      disabled={isIngesting}
                    />
                  </div>
                </div>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={renderJs}
                    onChange={(e) => setRenderJs(e.target.checked)}
                    disabled={isIngesting}
                  />
                  <span>Render JavaScript (Playwright Chromium)</span>
                </label>
              </div>
            )}
          </div>

          <button
            type="submit"
            className="btn-primary-3d"
            disabled={isIngesting || !url.trim()}
          >
            {isIngesting ? (
              <RefreshCw size={16} className="animate-spin" />
            ) : (
              <Play size={16} fill="#ffffff" />
            )}
            <span>{isIngesting ? 'Ingesting & Indexing...' : '1-Click Ingest & Index'}</span>
          </button>
        </form>

        {isIngesting && (
          <PipelineStepper currentStep={currentStep} error={ingestError} />
        )}
      </div>

      {/* Card 2: Knowledge Base Metrics */}
      <div className="card-3d">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div className="card-title" style={{ marginBottom: 0 }}>
            <Icon3DDatabase size={24} glow={true} />
            <span>Vector Knowledge Base</span>
          </div>

          <button
            type="button"
            className="btn-secondary"
            onClick={onRefreshStatus}
            title="Refresh status from backend"
          >
            <RefreshCw size={11} />
            <span>Sync</span>
          </button>
        </div>

        <div className="stats-grid-3d">
          <div className="stat-box-3d">
            <div className="stat-value">{pipelineStatus?.scraped_document_count ?? 0}</div>
            <div className="stat-label">Scraped Pages</div>
          </div>
          <div className="stat-box-3d">
            <div className="stat-value">{pipelineStatus?.chunked_document_count ?? 0}</div>
            <div className="stat-label">Chunked Docs</div>
          </div>
          <div className="stat-box-3d">
            <div className="stat-value" style={{ color: '#818cf8' }}>
              {pipelineStatus?.vector_count ?? 0}
            </div>
            <div className="stat-label">Indexed Vectors</div>
          </div>
          <div className="stat-box-3d">
            <div className="stat-value" style={{ color: '#34d399' }}>
              {pipelineStatus?.embedding_dimension ?? 384}d
            </div>
            <div className="stat-label">BGE Dimensions</div>
          </div>
        </div>

        <div style={{ marginTop: 14, fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <CheckCircle2 size={13} color="#10b981" />
          <span>Local Index: <code>data/vector_store/</code></span>
        </div>
      </div>
    </aside>
  );
}
