import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User, Sparkles, Clock } from 'lucide-react';
import SourceCard from './SourceCard';

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`message-row ${isUser ? 'user' : 'bot'}`}>
      <div className={`avatar ${isUser ? 'user' : 'bot'}`}>
        {isUser ? <User size={16} /> : <Bot size={16} />}
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
              {message.reframedQuery && message.reframedQuery !== message.originalQuery && (
                <span className="reframed-pill" title="Optimized query used for dense vector retrieval">
                  <Sparkles size={10} />
                  <span>Search key: "{message.reframedQuery}"</span>
                </span>
              )}
              {message.elapsed && (
                <span>
                  <Clock size={10} style={{ display: 'inline', marginRight: 3 }} />
                  {message.elapsed}s
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
