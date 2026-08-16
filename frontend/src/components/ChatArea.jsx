import React, { useState, useRef, useEffect } from 'react';
import { Send, Trash2, Sparkles, ArrowRight, Zap } from 'lucide-react';
import { Icon3DBot, Icon3DSparkles } from './Icons3D';
import ChatMessage from './ChatMessage';

export default function ChatArea({
  messages,
  onSendMessage,
  onClearChat,
  isLoading,
  vectorCount,
}) {
  const [inputText, setInputText] = useState('');
  const [enableReframing, setEnableReframing] = useState(true);
  const messagesEndRef = useRef(null);

  const suggestedQuestions = [
    { title: 'Catalog Overview', query: 'What books or categories are available in the catalog?' },
    { title: 'Specific Item Lookup', query: 'What is the price, availability, and description of "Lab Girl"?' },
    { title: 'Filtered Pricing Query', query: 'List all items priced under £20 with their stock status.' },
  ];

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!inputText.trim() || isLoading) return;
    onSendMessage(inputText.trim(), { reframe: enableReframing });
    setInputText('');
  };

  const handleSelectPrompt = (promptQuery) => {
    onSendMessage(promptQuery, { reframe: enableReframing });
  };

  return (
    <main className="chat-container">
      <div className="messages-stream">
        {messages.length === 0 ? (
          <div className="welcome-hero-3d">
            <div className="hero-3d-orb">
              <Icon3DBot size={72} glow={true} />
            </div>
            
            <h2 className="hero-title">Ask Your AI Knowledge Base</h2>
            <p className="hero-subtitle">
              {vectorCount > 0
                ? `Ready with ${vectorCount.toLocaleString()} neural-indexed vectors. Ask questions, compare items, extract facts, or summarize web data!`
                : 'No website indexed yet. Paste a target URL in the left sidebar and click "1-Click Ingest & Index" to start!'}
            </p>

            {vectorCount > 0 && (
              <div className="suggested-prompts-grid">
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textAlign: 'left', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon3DSparkles size={16} />
                  <span>Suggested Starter Questions:</span>
                </div>
                {suggestedQuestions.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="prompt-card-3d"
                    onClick={() => handleSelectPrompt(item.query)}
                  >
                    <div>
                      <div style={{ fontWeight: 600, color: '#f8fafc', fontSize: 13, marginBottom: 2 }}>{item.title}</div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{item.query}</div>
                    </div>
                    <ArrowRight size={16} color="#818cf8" style={{ flexShrink: 0, marginLeft: 12 }} />
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg, index) => (
            <ChatMessage key={index} message={msg} />
          ))
        )}

        {isLoading && (
          <div className="message-row bot">
            <div className="avatar-3d">
              <Icon3DBot size={32} glow={false} />
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Retrieving dense context & generating answer with Qwen2.5-1.5B...
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input Bar */}
      <footer className="chat-input-area">
        <form onSubmit={handleSubmit} className="input-box-wrapper">
          <input
            type="text"
            className="chat-input"
            placeholder={
              vectorCount > 0
                ? 'Ask a question about the ingested website (e.g. products, prices, summaries)...'
                : 'Ingest a website first or ask a question...'
            }
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isLoading}
          />

          <button
            type="submit"
            className="btn-send"
            disabled={!inputText.trim() || isLoading}
            title="Send Question (Enter)"
          >
            <Send size={16} />
          </button>
        </form>

        <div className="input-footer-controls">
          <label className="checkbox-label" style={{ margin: 0 }}>
            <input
              type="checkbox"
              checked={enableReframing}
              onChange={(e) => setEnableReframing(e.target.checked)}
            />
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <Zap size={12} color="#818cf8" />
              <span>Smart Search Reframing (Higher Accuracy)</span>
            </span>
          </label>

          {messages.length > 0 && (
            <button
              type="button"
              className="btn-text"
              onClick={onClearChat}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <Trash2 size={11} />
              <span>Clear History</span>
            </button>
          )}
        </div>
      </footer>
    </main>
  );
}
