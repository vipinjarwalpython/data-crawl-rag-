import React from 'react';
import { Icon3DBot, Icon3DSparkles, Icon3DDatabase, Icon3DShield } from './Icons3D';

export default function Header({ isHealthy, pipelineStatus }) {
  const vectorCount = pipelineStatus?.vector_count ?? 0;
  const llmModel = pipelineStatus?.llm_model || 'Qwen/Qwen2.5-1.5B-Instruct';
  const embeddingModel = pipelineStatus?.embedding_model || 'BAAI/bge-small-en-v1.5';

  return (
    <header className="app-header">
      <div className="brand-section">
        <Icon3DBot size={38} glow={true} />
        <div className="brand-info">
          <h1>CrawlRAG Studio</h1>
          <span>AI Web Knowledge Ingestion & Neural Q&A</span>
        </div>
      </div>

      <div className="header-badges">
        {/* Status Indicator */}
        <div className={`badge ${isHealthy ? 'badge-emerald' : 'badge-rose'}`}>
          <span
            className="pulse-dot"
            style={{ backgroundColor: isHealthy ? '#10b981' : '#f43f5e' }}
          />
          <span>{isHealthy ? 'Local AI Server Online' : 'Server Disconnected'}</span>
        </div>

        {/* Model Badge */}
        <div className="badge badge-indigo" title={`Active Generative Model: ${llmModel}`}>
          <Icon3DSparkles size={16} />
          <span>{llmModel.split('/')[1] || llmModel}</span>
        </div>

        {/* Vector Count Badge */}
        <div className="badge" title={`Vector Store: ${embeddingModel} (384-dim)`}>
          <Icon3DDatabase size={16} />
          <span>{vectorCount.toLocaleString()} Vectors</span>
        </div>
      </div>
    </header>
  );
}
