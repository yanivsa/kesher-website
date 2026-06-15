import { useRef, useState } from 'react';
import { submitContact } from '../lib/contactApi';

export const useContactForm = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    service: 'couples',
    message: ''
  });
  const [company, setCompany] = useState('');
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const startedAt = useRef(0);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitStatus('idle');

    try {
      setSubmitStatus('submitting');
      await submitContact({
        kind: 'contact',
        ...formData,
        company,
        startedAt: startedAt.current,
      });
      setSubmitStatus('success');
      setFormData({ name: '', email: '', phone: '', service: 'couples', message: '' });
      setCompany('');
      startedAt.current = 0;
    } catch {
      setSubmitStatus('error');
    }
  };

  const handleFocus = () => {
    if (!startedAt.current) startedAt.current = Date.now();
  };

  const resetStatus = () => {
    setSubmitStatus('idle');
  };

  return {
    formData,
    company,
    setCompany,
    submitStatus,
    handleChange,
    handleSubmit,
    handleFocus,
    resetStatus
  };
};
