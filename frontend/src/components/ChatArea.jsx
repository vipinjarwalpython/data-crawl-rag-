import React, { useState, useRef, useEffect } from 'react';
import { Send, Trash2, Sparkles, MessageSquare, ArrowRight, Bot } from 'lucide-react';
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
    'What books or categories are available in the catalog?',
    'What is the price, availability, and description of "Lab Girl"?',
    'List all items priced under £20 with stock status.',
  ];

  // Auto-scroll to bottom on new messages or loading states
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!inputText.trim() || isLoading) return;
    onSendMessage(inputText.trim(), { reframe: enableReframing });
    setInputText('');
  };

  const handleSelectPrompt = (prompt) => {
    onSendMessage(prompt, { reframe: enableReframing });
  };

  return (
    <main className="chat-container">
      <div className="messages-stream">
        {messages.length === 0 ? (
          <div className="welcome-hero">
            <div className="hero-icon">
              <Bot size={32} />
            </div>
            <h2 className="hero-title">Ask Your Knowledge Base</h2>
            <p className="hero-subtitle">
              {vectorCount > 0
                ? `Ready with ${vectorCount.toLocaleString()} indexed vectors. Ask anything about your crawled websites!`
                : 'No website indexed yet. Paste a URL in the left sidebar and click "1-Click Ingest & Index" to start!'}
            </p>

            {vectorCount > 0 && (
              <div className="suggested-prompts">
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textAlign: 'left', marginBottom: 4 }}>
                  Suggested Questions:
                </div>
                {suggestedQuestions.map((q, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="prompt-card-btn"
                    onClick={() => handleSelectPrompt(q)}
                  >
                    <span>{q}</span>
                    <ArrowRight size={14} color="#818cf8" />
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
            <div className="avatar bot">
              <Bot size={16} />
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Retrieving context & generating answer with Qwen2.5-1.5B...
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
                ? 'Ask a question about the ingested website (e.g. products, prices, facts)...'
                : 'Ingest a website first or ask a general query...'
            }
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isLoading}
          />

          <button
            type="submit"
            className="btn-send"
            disabled={!inputText.trim() || isLoading}
            title="Send Question"
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
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Sparkles size={11} color="#818cf8" />
              <span>Smart Search Reframing</span>
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
              <span>Clear Conversation</span>
            </button>
          )}
        </div>
      </footer>
    </main>
  );
}
