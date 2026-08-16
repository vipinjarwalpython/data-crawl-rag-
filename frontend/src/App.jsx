import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import {
  checkBackendHealth,
  fetchPipelineStatus,
  startWebsiteCrawl,
  buildRagIndex,
  askRagChatbot,
} from './api/client';

export default function App() {
  const [isHealthy, setIsHealthy] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isChatLoading, setIsChatLoading] = useState(false);

  // Ingestion workflow states
  const [isIngesting, setIsIngesting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [ingestError, setIngestError] = useState(null);

  // Load initial health & pipeline status
  const refreshStatus = useCallback(async () => {
    const health = await checkBackendHealth();
    setIsHealthy(health.healthy);

    if (health.healthy) {
      const status = await fetchPipelineStatus();
      if (status) setPipelineStatus(status);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, [refreshStatus]);

  // 1-Click Ingest & Index workflow
  const handleStartIngest = async (crawlOptions) => {
    setIsIngesting(true);
    setIngestError(null);
    setCurrentStep(1); // 1. Crawling

    try {
      // Step 1: Web Crawl
      const crawlResult = await startWebsiteCrawl(crawlOptions);
      console.log('Crawl complete:', crawlResult);

      // Step 2-4: Clean, Chunk, Embed in Vector DB
      setCurrentStep(2);
      await new Promise((r) => setTimeout(r, 600)); // smooth visual transition
      setCurrentStep(3);
      await new Promise((r) => setTimeout(r, 400));
      setCurrentStep(4);

      const indexResult = await buildRagIndex(32);
      console.log('Index complete:', indexResult);

      // Step 5: Refresh Knowledge Base metrics
      await refreshStatus();

      // Add a system welcome message in the chat
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `🎉 **Successfully ingested and indexed ${crawlResult.total_scraped || 1} pages from [${crawlOptions.url}](${crawlOptions.url})!**\n\nI have chunked the content and generated 384-dimensional vector embeddings with BGE. You can now ask me any question about this website.`,
          sources: [],
        },
      ]);
    } catch (err) {
      console.error('Ingestion error:', err);
      setIngestError(err.message || 'An error occurred during ingestion.');
    } finally {
      setIsIngesting(false);
      setCurrentStep(0);
    }
  };

  // Chat message submission
  const handleSendMessage = async (queryText, options) => {
    const startTime = performance.now();

    // 1. Append user message
    const userMsg = {
      role: 'user',
      content: queryText,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsChatLoading(true);

    try {
      // 2. Call backend RAG answer endpoint
      const response = await askRagChatbot(queryText, options);
      const elapsedSeconds = ((performance.now() - startTime) / 1000).toFixed(2);

      // 3. Append assistant response
      const assistantMsg = {
        role: 'assistant',
        content: response.answer || 'I could not generate an answer from the retrieved context.',
        sources: response.sources || [],
        reframedQuery: response.reframed_query,
        originalQuery: queryText,
        elapsed: elapsedSeconds,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error('Chat error:', err);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ **Error generating answer:** ${err.message || 'Check if the backend server is running at http://127.0.0.1:8000.'}`,
          sources: [],
        },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
  };

  return (
    <div className="app-container">
      <Header isHealthy={isHealthy} pipelineStatus={pipelineStatus} />

      <div className="main-layout">
        <Sidebar
          isHealthy={isHealthy}
          pipelineStatus={pipelineStatus}
          onRefreshStatus={refreshStatus}
          isIngesting={isIngesting}
          currentStep={currentStep}
          ingestError={ingestError}
          onStartIngest={handleStartIngest}
        />

        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          onClearChat={handleClearChat}
          isLoading={isChatLoading}
          vectorCount={pipelineStatus?.vector_count ?? 0}
        />
      </div>
    </div>
  );
}
