import React from 'react';

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'google-add-preferred-source-btn': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        'data-lang'?: string;
        'data-theme'?: string;
        'data-initialized'?: string;
      };
      'div': React.DetailedHTMLProps<React.HTMLAttributes<HTMLDivElement>, HTMLDivElement> & {
        'google-add-preferred-source-btn'?: string;
      };
    }
  }
}
