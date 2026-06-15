import { act, render, screen, cleanup } from '@testing-library/react';
import { useScrollReveal } from '../src/hooks/useScrollReveal';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';

describe('useScrollReveal', () => {
  let observeMock: ReturnType<typeof vi.fn>;
  let unobserveMock: ReturnType<typeof vi.fn>;
  let disconnectMock: ReturnType<typeof vi.fn>;
  let intersectionCallback: IntersectionObserverCallback;

  beforeEach(() => {
    observeMock = vi.fn();
    unobserveMock = vi.fn();
    disconnectMock = vi.fn();

    // Mock IntersectionObserver using a constructor function
    const MockIntersectionObserver = vi.fn();
    MockIntersectionObserver.mockImplementation(function(this: any, callback: IntersectionObserverCallback) {
      intersectionCallback = callback;
      this.observe = observeMock;
      this.unobserve = unobserveMock;
      this.disconnect = disconnectMock;
    });
    window.IntersectionObserver = MockIntersectionObserver as any;
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  const TestComponent = ({ options }: { options?: any }) => {
    const [ref, isVisible] = useScrollReveal(options);
    return (
      <div ref={ref as React.RefObject<HTMLDivElement>} data-testid="target">
        {isVisible ? 'Visible' : 'Hidden'}
      </div>
    );
  };

  it('should initialize correctly', () => {
    render(<TestComponent />);
    expect(screen.getByTestId('target').textContent).toBe('Hidden');
    expect(observeMock).toHaveBeenCalledTimes(1);
    expect(observeMock).toHaveBeenCalledWith(screen.getByTestId('target'));
  });

  it('should update visibility when intersection occurs (triggerOnce = true)', () => {
    render(<TestComponent options={{ triggerOnce: true }} />);

    expect(screen.getByTestId('target').textContent).toBe('Hidden');

    // Simulate intersection
    act(() => {
      intersectionCallback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
    });

    expect(screen.getByTestId('target').textContent).toBe('Visible');
    // Because triggerOnce is true, it should unobserve
    expect(unobserveMock).toHaveBeenCalledTimes(1);
    expect(unobserveMock).toHaveBeenCalledWith(screen.getByTestId('target'));

    // Further intersections shouldn't do anything since it unobserved, but let's test the hook's behavior anyway
    act(() => {
      intersectionCallback([{ isIntersecting: false } as IntersectionObserverEntry], {} as IntersectionObserver);
    });

    // Should still be visible
    expect(screen.getByTestId('target').textContent).toBe('Visible');
  });

  it('should update visibility when intersection occurs (triggerOnce = false)', () => {
    render(<TestComponent options={{ triggerOnce: false }} />);

    expect(screen.getByTestId('target').textContent).toBe('Hidden');

    // Simulate intersecting
    act(() => {
      intersectionCallback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
    });

    expect(screen.getByTestId('target').textContent).toBe('Visible');
    expect(unobserveMock).not.toHaveBeenCalled();

    // Simulate leaving intersection
    act(() => {
      intersectionCallback([{ isIntersecting: false } as IntersectionObserverEntry], {} as IntersectionObserver);
    });

    expect(screen.getByTestId('target').textContent).toBe('Hidden');
  });

  it('should disconnect observer on unmount', () => {
    const { unmount } = render(<TestComponent />);
    unmount();
    expect(disconnectMock).toHaveBeenCalledTimes(1);
  });
});
