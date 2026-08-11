import { describe, expect, it, vi, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LeadMagnet from '../src/components/LeadMagnet/LeadMagnet';
import * as contactApi from '../src/lib/contactApi';

vi.mock('../src/lib/contactApi', () => ({
  submitContact: vi.fn(),
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe('LeadMagnet component', () => {
  it('displays an accessible error state when submitContact rejects', async () => {
    vi.mocked(contactApi.submitContact).mockRejectedValue(new Error('Submission failed'));

    render(React.createElement(LeadMagnet));

    const emailInput = screen.getByLabelText('כתובת אימייל');
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    const submitBtn = screen.getByRole('button', { name: /קבלת קישור להורדה/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      const errorMsg = screen.getByRole('alert');
      expect(errorMsg).toBeDefined();
      expect(errorMsg.textContent).toContain('לא הצלחנו לשלוח את הבקשה');
    });
  });
});
