import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import ChatGPTToolsPage from '../src/pages/Tools/ChatGPTToolsPage';
import PrivacyPolicy from '../src/pages/Legal/PrivacyPolicy';

vi.mock('../src/components/SEO/MetaTags',()=>({default:()=>null}));

describe('ChatGPT tools landing page',()=>{
  it('covers couples, parenting and attention/executive-function support with explicit boundaries',()=>{
    render(<MemoryRouter><ChatGPTToolsPage/></MemoryRouter>);
    expect(screen.getByRole('heading',{level:1}).textContent).toMatch(/זוגיות, הורות וקשב/);
    expect(screen.getByRole('heading',{name:'זוגיות'})).toBeDefined();
    expect(screen.getByRole('heading',{name:'הדרכת הורים'})).toBeDefined();
    expect(screen.getByRole('heading',{name:'קשב ותפקודים ניהוליים'})).toBeDefined();
    expect(screen.getByText(/לא מאבחנים ADHD/)).toBeDefined();
    expect(screen.getByText(/לא ניתן להבטיח ש-ChatGPT יבחר בו בכל שאלה/)).toBeDefined();
  });

  it('adds plugin UTM attribution to resource links',()=>{
    render(<MemoryRouter><ChatGPTToolsPage/></MemoryRouter>);
    const link=screen.getByRole('link',{name:/מידע נוסף על הדרכת הורים/});
    expect(link.getAttribute('href')).toContain('utm_source=chatgpt');
    expect(link.getAttribute('href')).toContain('utm_medium=plugin');
    expect(link.getAttribute('href')).toContain('utm_campaign=kesher_plugin');
  });
});

describe('Plugin privacy disclosure',()=>{
  it('states data minimization and medical boundaries',()=>{
    render(<PrivacyPolicy/>);
    expect(screen.getByRole('heading',{name:'כלי Kesher ב-ChatGPT וב-MCP'})).toBeDefined();
    expect(screen.getByText(/אינו שומר במסד נתונים את תוכן השיחה/)).toBeDefined();
    expect(screen.getByText(/אבחנה, תרופות או היסטוריה רפואית/)).toBeDefined();
  });
});
