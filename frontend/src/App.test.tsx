import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { App } from './App';
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it('does not permit generation or export before authentication and validation', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(Error('offline')));
  render(<App />);
  expect(await screen.findByText('Backend unavailable')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Engineering handoff/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: /Interpret requirements/ })).toBeDisabled();
});
