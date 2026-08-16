import React, { useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Sparkles, Clock, Copy, Check } from 'lucide-react';
import { Icon3DBot } from './Icons3D';
import SourceCard from './SourceCard';

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`message-row ${isUser ? 'user' : 'bot'}`}>
      <div className="avatar-3d">
        {isUser ? (
          <div style={{ width: 34, height: 34, borderRadius: 10, background: 'linear-gradient(135deg, #334155 0%, #1e293b 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(255,255,255,0.1)' }}>
            <User size={16} color="#f8fafc" />
          </div>
        ) : (
          <Icon3DBot size={34} glow={false} />
        )}
      </div>

      <div className="message-content">
        <div className="message-bubble">
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <Markdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </Markdown>
          )}
        </div>

        {!isUser && (
          <>
            {message.sources && message.sources.length > 0 && (
              <SourceCard sources={message.sources} />
            )}

            <div className="message-meta">
              <div className="meta-tags-left">
                {message.reframedQuery && message.reframedQuery !== message.originalQuery && (
                  <span className="reframed-pill" title="Optimized query used for dense vector retrieval">
                    <Sparkles size={10} />
                    <span>Key: "{message.reframedQuery}"</span>
                  </span>
                )}
                {message.elapsed && (
                  <span>
                    <Clock size={11} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                    {message.elapsed}s
                  </span>
                )}
              </div>

              <button
                type="button"
                className="btn-copy-small"
                onClick={handleCopy}
                title="Copy answer to clipboard"
              >
                {copied ? <Check size={11} color="#34d399" /> : <Copy size={11} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
