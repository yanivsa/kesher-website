import React, { useEffect, useState } from 'react';
import { FiMessageCircle } from 'react-icons/fi';
import './AIChatbot.css';

const CONSENT_KEY = 'kesher-ai-chat-consent';
const SCRIPT_URL = 'https://unpkg.com/@elevenlabs/convai-widget-embed@0.8.1/dist/index.js';

const AIChatbot: React.FC = () => {
  const [consented, setConsented] = useState(() => localStorage.getItem(CONSENT_KEY) === 'yes');
  const [scriptLoaded, setScriptLoaded] = useState(false);

  useEffect(() => {
    if (!consented) return;

    const existingScript = document.querySelector<HTMLScriptElement>('script[data-kesher-ai-chat]');
    if (existingScript) {
      queueMicrotask(() => setScriptLoaded(true));
      return;
    }

    const script = document.createElement('script');
    script.src = SCRIPT_URL;
    script.async = true;
    script.crossOrigin = 'anonymous';
    script.integrity = 'sha384-xAcN9ZVkolOzxxKgR7KnzBpuVW7VKHhxLT+SRsWwD0oaLf5C9l2F7GhUG4mctZvC';
    script.dataset.kesherAiChat = 'true';
    script.onload = () => setScriptLoaded(true);
    document.body.appendChild(script);
  }, [consented]);

  if (!consented) {
    return (
      <button
        type="button"
        className="ai-chat-consent"
        onClick={() => {
          localStorage.setItem(CONSENT_KEY, 'yes');
          setConsented(true);
        }}
        aria-label="הפעלת צ'אט עם עוזרת AI חיצונית"
      >
        <FiMessageCircle className="ai-chat-icon" aria-hidden="true" />
        <span className="ai-chat-text">עזרה</span>
      </button>
    );
  }

  if (!scriptLoaded) return null;

  return React.createElement('elevenlabs-convai', {
    'agent-id': 'agent_2201kthm21rbejr80f69dgq03dhv',
    variant: 'expandable',
    'avatar-orb-color-1': '#4A6854',
    'avatar-orb-color-2': '#945035',
    'action-text': "צ'אט עם עוזרת ה-AI שלנו",
    'start-call-text': "התחלת צ'אט",
    'end-call-text': "סיום צ'אט",
    'disable-banner': 'true',
  });
};

export default AIChatbot;
