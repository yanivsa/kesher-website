import React, { useEffect, useState } from 'react';
import './AIChatbot.css';

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'elevenlabs-convai': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement> & {
        'agent-id': string;
        'variant'?: 'compact' | 'expanded';
        'action-text'?: string;
        'start-call-text'?: string;
        'end-call-text'?: string;
        'avatar-image-url'?: string;
        'avatar-orb-color-1'?: string;
        'avatar-orb-color-2'?: string;
        'disable-banner'?: string;
      }, HTMLElement>;
    }
  }
}

const AIChatbot: React.FC = () => {
  const [scriptLoaded, setScriptLoaded] = useState(false);

  useEffect(() => {
    // Check if the script is already present in the DOM
    const existingScript = document.querySelector('script[src*="convai-widget"]');
    if (existingScript) {
      setScriptLoaded(true);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/@elevenlabs/convai-widget-embed';
    script.async = true;
    script.onload = () => {
      setScriptLoaded(true);
    };
    script.onerror = (e) => {
      console.error('Failed to load ElevenLabs Convai Widget script:', e);
    };
    document.body.appendChild(script);

    return () => {
      // The script is global and is kept, but check on mount prevents duplication.
    };
  }, []);

  if (!scriptLoaded) return null;

  return (
    <elevenlabs-convai
      agent-id="agent_2201kthm21rbejr80f69dgq03dhv"
      avatar-orb-color-1="#7C9E87" /* Primary color from variables: sage green */
      avatar-orb-color-2="#C07B5A" /* Accent color: warm terracotta */
      action-text="דברו עם יועצת ה-AI שלנו"
      start-call-text="התחלת שיחה"
      end-call-text="סיום שיחה"
      disable-banner="true"
    />
  );
};

export default AIChatbot;
