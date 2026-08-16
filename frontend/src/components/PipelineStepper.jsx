import React from 'react';
import { Check, Loader2 } from 'lucide-react';

export default function PipelineStepper({ currentStep, error }) {
  const steps = [
    { id: 1, title: 'Crawling Target Website' },
    { id: 2, title: 'Text Cleaning & Noise Filter' },
    { id: 3, title: 'Semantic Chunking (400 chars)' },
    { id: 4, title: 'Embedding & Vector Indexing' },
  ];

  if (!currentStep) return null;

  return (
    <div className="stepper-container">
      {steps.map((step) => {
        const isDone = currentStep > step.id;
        const isActive = currentStep === step.id;

        return (
          <div
            key={step.id}
            className={`step-item ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
          >
            <div className="step-icon">
              {isDone ? (
                <Check size={12} />
              ) : isActive ? (
                <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                step.id
              )}
            </div>
            <span>{step.title}</span>
          </div>
        );
      })}

      {error && (
        <div style={{ color: '#f43f5e', fontSize: 12, marginTop: 6, padding: '6px 10px', background: 'rgba(244,63,94,0.1)', borderRadius: 6 }}>
          {error}
        </div>
      )}
    </div>
  );
}
