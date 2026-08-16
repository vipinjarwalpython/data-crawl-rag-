import React, { useState } from 'react';
import { BookOpen, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';

export default function SourceCard({ sources }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="sources-container">
      <button
        type="button"
        className="sources-toggle-btn"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <BookOpen size={13} />
        <span>{sources.length} Context Sources Used</span>
        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>

      {isExpanded && (
        <div className="sources-list">
          {sources.map((src, index) => {
            const scorePercent = Math.round((src.score || 0) * 100);
            return (
              <div key={src.chunk_id || index} className="source-item-card">
                <div className="source-header">
                  <a
                    href={src.url || '#'}
                    target="_blank"
                    rel="noreferrer"
                    className="source-title"
                  >
                    <span>{src.title || 'Source Document'}</span>
                    <ExternalLink size={11} />
                  </a>
                  <span className="score-badge">
                    {scorePercent}% Match
                  </span>
                </div>
                <div className="source-snippet">
                  {src.text}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
