import React from 'react';
import { Bot, Sparkles, Activity, Layers } from 'lucide-react';

export default function Header({ isHealthy, pipelineStatus }) {
  const vectorCount = pipelineStatus?.vector_count ?? 0;
  const llmModel = pipelineStatus?.llm_model || 'Qwen2.5-1.5B-Instruct';

  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo">
          <Bot size={20} />
        </div>
        <div className="brand-info">
          <h1>CrawlRAG Assistant</h1>
          <span>AI Web Knowledge Ingestion & Semantic Q&A</span>
        </div>
      </div>

      <div className="header-badges">
        <div className={`badge ${isHealthy ? 'badge-emerald' : 'badge-rose'}`}>
          <span className="pulse-dot" style={{ backgroundColor: isHealthy ? '#10b981' : '#f43f5e' }} />
          <span>{isHealthy ? 'Backend Online' : 'Backend Disconnected'}</span>
        </div>

        <div className="badge badge-indigo">
          <Sparkles size={12} />
          <span>{llmModel.split('/')[1] || llmModel}</span>
        </div>

        <div className="badge">
          <Layers size={12} color="#94a3b8" />
          <span>{vectorCount.toLocaleString()} Vectors</span>
        </div>
      </div>
    </header>
  );
}
