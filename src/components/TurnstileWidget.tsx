import React, { useEffect, useRef, useState } from 'react';

type TurnstileApi = {
  render: (
    container: HTMLElement,
    options: {
      sitekey: string;
      action: string;
      callback: (token: string) => void;
      'expired-callback': () => void;
      'error-callback': () => void;
    },
  ) => string;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

type TurnstileWidgetProps = {
  action: 'contact' | 'lead_magnet';
  onTokenChange: (token: string) => void;
  resetKey?: number;
};

let scriptPromise: Promise<void> | null = null;

const loadTurnstileScript = () => {
  if (typeof window === 'undefined') return Promise.resolve();
  if (window.turnstile) return Promise.resolve();
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      'script[data-kesher-turnstile]',
    );

    const handleLoad = () => {
      if (window.turnstile) {
        resolve();
      } else {
        reject(new Error('Turnstile loaded without exposing its API'));
      }
    };
    const handleError = () => reject(new Error('Turnstile script failed to load'));

    if (existing) {
      existing.addEventListener('load', handleLoad, { once: true });
      existing.addEventListener('error', handleError, { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.dataset.kesherTurnstile = 'true';
    script.addEventListener('load', handleLoad, { once: true });
    script.addEventListener('error', handleError, { once: true });
    document.head.appendChild(script);
  }).catch((error) => {
    scriptPromise = null;
    throw error;
  });

  return scriptPromise;
};

const TurnstileWidget: React.FC<TurnstileWidgetProps> = ({
  action,
  onTokenChange,
  resetKey = 0,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let disposed = false;
    let widgetId: string | null = null;
    onTokenChange('');
    queueMicrotask(() => {
      if (!disposed) setStatus('loading');
    });

    const initialize = async () => {
      try {
        const response = await fetch('/api/turnstile-config', {
          headers: { Accept: 'application/json' },
          credentials: 'same-origin',
          cache: 'no-store',
        });
        if (!response.ok) throw new Error('Turnstile configuration unavailable');
        const data = await response.json() as { siteKey?: unknown };
        const siteKey = typeof data.siteKey === 'string' ? data.siteKey.trim() : '';
        if (!siteKey) throw new Error('Turnstile site key is missing');

        await loadTurnstileScript();
        if (disposed || !containerRef.current || !window.turnstile) return;

        widgetId = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          action,
          callback: (token) => {
            if (disposed) return;
            onTokenChange(token);
            setStatus('ready');
          },
          'expired-callback': () => {
            if (disposed) return;
            onTokenChange('');
            setStatus('loading');
          },
          'error-callback': () => {
            if (disposed) return;
            onTokenChange('');
            setStatus('error');
          },
        });
      } catch {
        if (!disposed) {
          onTokenChange('');
          setStatus('error');
        }
      }
    };

    void initialize();

    return () => {
      disposed = true;
      onTokenChange('');
      if (widgetId && window.turnstile) {
        window.turnstile.remove(widgetId);
      }
    };
  }, [action, onTokenChange, resetKey]);

  return (
    <div aria-live="polite">
      <div ref={containerRef} />
      {status === 'loading' && <small>בדיקת אבטחה נטענת…</small>}
      {status === 'error' && (
        <small role="alert">
          בדיקת האבטחה אינה זמינה כרגע. אפשר לנסות לרענן את העמוד או לפנות בוואטסאפ.
        </small>
      )}
    </div>
  );
};

export default TurnstileWidget;
