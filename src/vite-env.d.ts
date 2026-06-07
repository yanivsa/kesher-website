declare module "*.module.css";
declare module "*.module.scss";

declare global {
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

