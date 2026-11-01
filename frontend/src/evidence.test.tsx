import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from './App';

// API fixtures exercise presentation guards only; native CAD is tested separately in Chromium.
const spec = {
  schema_version: 1,
  part_family: 'plate',
  units: 'mm',
  parameters: { length_mm: 60, width_mm: 25, thickness_mm: 5, corner_radius_mm: 0 },
  hole_features: [],
  assumptions: [],
  source_text: 'Plate 60 x 25 x 5 mm.',
};
const constraints = {
  valid: true,
  checks: [{ check: 'prebuild_constraints', status: 'pass' }],
  warnings: [],
};
function service() {
  const project = {
    id: 'project-test',
    name: 'Fixture plate',
    head_id: 'revision-test',
    created_at: '2026-10-31T00:00:00Z',
    revisions: [],
  };
  const revision = {
    id: 'revision-test',
    project_id: project.id,
    parent_id: null,
    spec,
    diff: [],
    created_at: project.created_at,
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      const route = String(input);
      let data: unknown;
      if (route === '/api/health') data = { ready: true };
      else if (route === '/api/sessions')
        data = { token: 'unit-token', session_id: 'session-test' };
      else if (route === '/api/projects' && init?.method === 'POST') data = project;
      else if (route === '/api/projects') data = [];
      else if (route.endsWith('/parse'))
        data = {
          status: 'ready',
          parsed_spec: spec,
          questions: [],
          source_attribution: [],
          validation: constraints,
        };
      else if (route.endsWith('/validate')) data = constraints;
      else if (route.endsWith('/revisions')) data = revision;
      else if (route === `/api/projects/${project.id}`) data = project;
      else if (route.endsWith('/generate'))
        data = { id: 'job-test', revision_id: revision.id, state: 'queued', error_code: null };
      else if (route === '/api/jobs/job-test')
        data = {
          id: 'job-test',
          revision_id: revision.id,
          state: 'failed',
          error_code: 'GENERATION_TIMEOUT',
        };
      else throw Error(`Unexpected test request ${route}`);
      return { ok: true, json: async () => data };
    }),
  );
}
async function interpret() {
  fireEvent.change(screen.getByLabelText('Local secret'), { target: { value: 'fixture-secret' } });
  fireEvent.click(screen.getByRole('button', { name: /Connect workspace/ }));
  await waitFor(() => expect(screen.queryByLabelText('Local secret')).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole('button', { name: /Interpret requirements/ }));
  await screen.findByLabelText('thickness_mm');
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it('a failed worker preserves confirmed source without enabling a validated export', async () => {
  service();
  const { container } = render(<App />);
  await interpret();
  fireEvent.click(screen.getByRole('checkbox', { name: /I reviewed dimensions/ }));
  fireEvent.click(screen.getByRole('button', { name: /Confirm & generate/ }));
  await waitFor(
    () => expect(container.querySelector('.build-summary')).toHaveTextContent('Build failed'),
    { timeout: 3500 },
  );
  expect(container.querySelector('.build-feedback')).toHaveTextContent('GENERATION_TIMEOUT');
  expect(screen.getByText(/confirmed source/, { selector: 'small' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Engineering handoff/ })).toBeDisabled();
  expect(screen.queryByText('Validated geometry', { exact: true })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Retry geometry' })).toBeEnabled();
});
it('editing after a constraint check invalidates the displayed prebuild pass', async () => {
  service();
  render(<App />);
  await interpret();
  fireEvent.change(screen.getByLabelText('thickness_mm'), { target: { value: '7' } });
  fireEvent.click(screen.getByRole('button', { name: 'Validation' }));
  expect(screen.getByText('CHECK AGAIN AFTER EDITS')).toBeInTheDocument();
  expect(screen.getByText(/Prebuild parameters only/)).toBeInTheDocument();
  expect(screen.queryByText('CHECKS PASSED', { exact: true })).not.toBeInTheDocument();
});
