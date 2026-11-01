import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import {
  api,
  download,
  type Auth,
  type Evaluation,
  type Job,
  type Parsed,
  type Project,
  type Revision,
  type Spec,
  type Validation,
} from './api';
import { parseDraft } from './draft';
import { Icon, Notice, ParameterField, Status, StudioNav } from './ui';
const Viewer = lazy(() => import('./Viewer').then((m) => ({ default: m.Viewer })));
const samples = [
  {
    family: 'plate',
    name: 'Mounting plate',
    icon: '▱',
    text: 'Make a 60 x 25 mm base plate, 5 mm thick, with four 4.5 mm clearance holes spaced 40 x 15 mm.',
  },
  {
    family: 'bracket',
    name: 'L-bracket',
    icon: '∟',
    text: 'L-bracket with base length 60 mm, width 30 mm, upright height 40 mm, thickness 5 mm.',
  },
  {
    family: 'enclosure',
    name: 'Electronics enclosure',
    icon: '▣',
    text: 'Electronics enclosure length 80 mm, width 50 mm, height 30 mm, wall thickness 3 mm, lid clearance 0.3 mm.',
  },
  {
    family: 'finger',
    name: 'Gripper finger',
    icon: '⌁',
    text: 'Gripper finger length 80 mm, width 20 mm, thickness 6 mm, tapered tip, taper length 20 mm, pad depth 1 mm.',
  },
];
const tabs = [
  'Design studio',
  'Revision history',
  'Validation',
  'Exports',
  'Evaluation',
  'Field guide',
];
const pretty = (v: unknown) => JSON.stringify(v, null, 2);
function specKey(spec: Spec | null): string {
  const ordered = (value: unknown): unknown =>
    Array.isArray(value)
      ? value.map(ordered)
      : value && typeof value === 'object'
        ? Object.fromEntries(
            Object.entries(value)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([key, val]) => [key, ordered(val)]),
          )
        : value;
  return JSON.stringify(ordered(spec));
}
export function App() {
  const [auth, setAuth] = useState<Auth | null>(null);
  const [secret, setSecret] = useState('');
  const [tab, setTab] = useState('Design studio');
  const [dark, setDark] = useState(false);
  const [health, setHealth] = useState('Checking CAD worker…');
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [projectName, setProjectName] = useState('Mounting plate study');
  const [revision, setRevision] = useState<Revision | null>(null);
  const [prompt, setPrompt] = useState(samples[0].text);
  const [clarification, setClarification] = useState('');
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [editor, setEditor] = useState('');
  const [draft, setDraft] = useState<Spec | null>(null);
  const [editorError, setEditorError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [viewId, setViewId] = useState<string | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [pane, setPane] = useState<'model' | 'requirements' | 'parameters'>('model');
  const [constraintsSignature, setConstraintsSignature] = useState('');
  const draftChanged = !!(draft && revision && specKey(draft) !== specKey(revision.spec));
  const geometricEvidence = !!validation?.bbox_mm;
  const validationFresh = geometricEvidence || constraintsSignature === specKey(draft);
  const buildLabel =
    job?.state === 'failed'
      ? 'Build failed · source saved'
      : job?.state === 'cancelled'
        ? 'Build cancelled · source saved'
        : job?.state === 'running'
          ? 'Building geometry'
          : job?.state === 'queued'
            ? 'Build queued'
            : draftChanged
              ? 'Uncommitted draft'
              : job?.state === 'completed'
                ? 'Validated geometry'
                : revision
                  ? 'Source saved · not built'
                  : draft
                    ? 'Draft awaiting confirmation'
                    : 'New design';
  const buildTone =
    job?.state === 'failed'
      ? 'danger'
      : job?.state === 'cancelled' || draftChanged
        ? 'warning'
        : job?.state === 'completed'
          ? 'good'
          : 'neutral';
  const running = job?.state === 'queued' || job?.state === 'running';
  const jobId = job?.id;
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }, [dark]);
  useEffect(() => {
    let alive = true;
    const check = () =>
      api<{ ready: boolean }>('/health', null)
        .then((h) => {
          if (alive) setHealth(h.ready ? 'CAD worker ready' : 'CAD worker unavailable');
        })
        .catch(() => {
          if (alive) setHealth('Backend unavailable');
        });
    check();
    const t = setInterval(check, 4000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  const refreshProjects = useCallback(async () => {
    if (auth) setProjects(await api<Project[]>('/projects', auth));
  }, [auth]);
  useEffect(() => {
    refreshProjects().catch((e) => setError(e.message));
  }, [refreshProjects]);
  useEffect(() => {
    if (!auth || !jobId || !running) return;
    let alive = true;
    const poll = () =>
      api<Job>(`/jobs/${jobId}`, auth).then((j) => {
        if (!alive) return;
        setJob(j);
        if (j.state === 'completed') {
          setViewId(j.revision_id);
          setPane('model');
          setValidation(j.validation ?? null);
          setNotice(
            'Geometry and export readback passed. This revision is ready to preview and download.',
          );
        }
        if (j.state === 'failed')
          setError(
            `Generation failed: ${j.error_code}. Your revision is saved; correct its parameters or retry.`,
          );
      });
    const timer = setInterval(() => poll().catch((e) => setError(e.message)), 1000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [auth, jobId, running]);
  async function action(work: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function setSpec(spec: Spec) {
    setDraft(spec);
    setEditor(pretty(spec));
    setEditorError('');
    setConfirmed(false);
  }
  function editJSON(text: string) {
    setEditor(text);
    setConfirmed(false);
    try {
      const s = parseDraft(text);
      setDraft(s);
      setEditorError('');
    } catch (e) {
      setEditorError((e as Error).message);
    }
  }
  async function parse(text = prompt) {
    const result = await api<Parsed>('/parse', auth, {
      text,
      current_revision_id: revision?.id ?? null,
    });
    setParsed(result);
    if (result.parsed_spec || result.partial_spec)
      setSpec((result.parsed_spec ?? result.partial_spec)!);
    else {
      setDraft(null);
      setEditor('');
    }
    setValidation(result.validation ?? null);
    setConstraintsSignature(specKey(result.parsed_spec ?? result.partial_spec ?? null));
    setPane(result.status === 'needs_clarification' ? 'requirements' : 'parameters');
    setConfirmed(false);
  }
  async function openProject(id: string) {
    const next = await api<Project>(`/projects/${id}`, auth);
    setProject(next);
    setProjectName(next.name);
    setParsed(null);
    setConfirmed(false);
    if (next.head_id) await selectRevision(next.head_id);
    else {
      setRevision(null);
      setViewId(null);
      setDraft(null);
      setEditor('');
    }
  }
  async function selectRevision(id: string) {
    const next = await api<Revision>(`/revisions/${id}`, auth);
    setRevision(next);
    setSpec(next.spec);
    setJob(next.generation ?? null);
    setViewId(next.generation ? id : null);
    setValidation(next.generation?.validation ?? null);
    setParsed(null);
    setPrompt('Increase thickness to 6 mm.');
    setTab('Design studio');
    setPane('model');
  }
  function newDesign(sample = samples[0]) {
    setError('');
    setNotice('');
    setConstraintsSignature('');
    setPane('requirements');
    setProject(null);
    setProjectName(`${sample.name} study`);
    setRevision(null);
    setJob(null);
    setParsed(null);
    setViewId(null);
    setValidation(null);
    setDraft(null);
    setEditor('');
    setPrompt(sample.text);
    setConfirmed(false);
    setTab('Design studio');
  }
  async function generate() {
    if (!draft || !auth || !confirmed) return;
    const report = await api<Validation>('/validate', auth, JSON.parse(editor));
    setValidation(report);
    setConstraintsSignature(specKey(JSON.parse(editor)));
    if (!report.valid)
      throw Error(report.errors?.map((e) => e.message).join('; ') ?? 'Prebuild validation failed');
    let active = project;
    if (!active) active = await api<Project>('/projects', auth, { name: projectName });
    const committed = await api<Revision>(`/projects/${active.id}/revisions`, auth, {
      spec: JSON.parse(editor),
      parent_id: active.head_id,
      confirmed: true,
    });
    setRevision(committed);
    const refreshed = await api<Project>(`/projects/${active.id}`, auth);
    setProject(refreshed);
    setConfirmed(false);
    setJob(await api<Job>(`/revisions/${committed.id}/generate`, auth, {}));
    await refreshProjects();
  }
  function editParameter(key: string, value: number | string) {
    if (draft) setSpec({ ...draft, parameters: { ...draft.parameters, [key]: value } });
  }
  const exportFile = (format: string) =>
    auth &&
    viewId &&
    action(() =>
      download(
        `/revisions/${viewId}/${format === 'zip' ? 'handoff' : `downloads/${format}`}`,
        auth,
        `text2cad-${viewId.slice(0, 8)}.${format === 'report' ? 'json' : format}`,
      ),
    );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to workspace
      </a>
      <StudioNav
        tabs={tabs}
        active={tab}
        onSelect={(name) => {
          setTab(name);
          if (name === 'Evaluation' && auth)
            action(async () => setEvaluation(await api<Evaluation>('/evaluation', auth)));
        }}
        onNew={() => newDesign()}
        projects={projects}
        selectedProject={project?.id ?? null}
        onProject={(id) => action(() => openProject(id))}
        dark={dark}
        onTheme={() => setDark(!dark)}
        connected={!!auth}
      />
      <div className="app-content">
        <header className="topbar">
          <div className="project-identity">
            <span className="project-icon">
              <Icon name="cube" />
            </span>
            <div>
              {project ? (
                <strong className="project-name">{projectName}</strong>
              ) : (
                <input
                  aria-label="Project name"
                  title={projectName}
                  value={projectName}
                  maxLength={100}
                  onChange={(event) => setProjectName(event.target.value)}
                />
              )}
              <small>
                {revision
                  ? `Revision ${revision.id.slice(0, 8)} · confirmed source`
                  : 'New project · saved after confirmation'}
              </small>
            </div>
          </div>
          <div className="build-summary" role="status" aria-live="polite" aria-atomic="true">
            <Status tone={buildTone}>{buildLabel}</Status>
            <span className="health">{health}</span>
          </div>
          <div className="toolbar-actions">
            {running && (
              <button onClick={() => action(() => api(`/jobs/${job?.id}/cancel`, auth, {}))}>
                Cancel active build
              </button>
            )}
            <button
              className="handoff-button"
              disabled={!auth || !viewId}
              onClick={() => exportFile('zip')}
            >
              <Icon name="download" />
              Engineering handoff
            </button>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} data-view={tab}>
          {tab !== 'Design studio' && (
            <div className="page-heading">
              <div>
                <h1>{tab}</h1>
                <p>
                  {project
                    ? `${project.name} · ${revision ? `selected revision ${revision.id.slice(0, 8)}` : 'no revision selected'}`
                    : 'Open a project to inspect its engineering record'}
                </p>
              </div>
            </div>
          )}
          {error && (
            <Notice tone="error" onDismiss={() => setError('')}>
              <strong>Action needs attention</strong>
              <span>{error}</span>
            </Notice>
          )}
          {notice && <Notice onDismiss={() => setNotice('')}>{notice}</Notice>}
          {!auth && (
            <form
              className="login panel"
              onSubmit={(e) => {
                e.preventDefault();
                action(async () => {
                  setAuth(await api<Auth>('/sessions', null, { secret }));
                  setSecret('');
                });
              }}
            >
              <div>
                <strong>Your local design workspace</strong>
                <p>
                  Connect with the secret in <code>.env</code> to save, generate, and export.
                </p>
              </div>
              <label>
                Local secret
                <input
                  aria-label="Local secret"
                  type="password"
                  autoComplete="current-password"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  required
                />
              </label>
              <button className="primary" disabled={busy}>
                Connect workspace
              </button>
            </form>
          )}
          {tab === 'Design studio' && (
            <>
              <div className="studio-toolbar">
                <div className="workspace-panes" aria-label="Workspace panes">
                  {(['model', 'requirements', 'parameters'] as const).map((name) => (
                    <button
                      key={name}
                      aria-pressed={pane === name}
                      aria-controls={`studio-${name}`}
                      onClick={() => setPane(name)}
                    >
                      <Icon
                        name={
                          name === 'model' ? 'cube' : name === 'requirements' ? 'edit' : 'sliders'
                        }
                      />
                      {name[0].toUpperCase() + name.slice(1)}
                    </button>
                  ))}
                </div>
                <span className="studio-scope">
                  {viewId
                    ? `Viewing geometry ${viewId.slice(0, 8)} · mm`
                    : 'Four supported families · millimeters'}
                </span>
              </div>
              {draftChanged && (
                <div className="draft-banner">
                  <Status tone="warning">Draft differs from confirmed source</Status>
                  <span>
                    The viewport and exports still show revision{' '}
                    {viewId?.slice(0, 8) ?? 'not generated'}.
                  </span>
                </div>
              )}
              <div className="studio-grid" data-pane={pane}>
                <section
                  className="panel prompt-panel"
                  id="studio-requirements"
                  aria-label="Requirements"
                >
                  <div className="panel-heading">
                    <strong>{revision ? 'Revision request' : 'Design requirements'}</strong>
                    <span className="tag">RULE PARSER</span>
                  </div>
                  <div className="prompt-body">
                    <div className="conversation-label">
                      {revision ? 'Describe a revision' : 'What would you like to build?'}
                    </div>
                    <p className="input-help">
                      Use explicit dimensions and units. Critical missing details become questions.
                    </p>
                    <label className="sr-only" htmlFor="prompt">
                      Design request
                    </label>
                    <textarea
                      id="prompt"
                      className="prompt-input"
                      value={prompt}
                      maxLength={4000}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="A 60 × 25 mm mounting plate…"
                    />
                    <div className="input-footer">
                      <span>{prompt.length} / 4000</span>
                      <span>mm · cm · m · inches</span>
                    </div>
                    <button
                      className="primary full"
                      disabled={!auth || busy || !prompt.trim() || running}
                      onClick={() => action(() => parse())}
                    >
                      Interpret {revision ? 'change' : 'requirements'} <span>↗</span>
                    </button>
                    {parsed && (
                      <div className={`parse-result ${parsed.status === 'ready' ? 'ready' : ''}`}>
                        <div>
                          <i />
                          {parsed.status === 'ready'
                            ? 'Requirements extracted'
                            : parsed.status.replaceAll('_', ' ')}
                        </div>
                        {parsed.questions.length > 0 && (
                          <ul>
                            {parsed.questions.map((q, i) => (
                              <li key={i}>{q}</li>
                            ))}
                          </ul>
                        )}
                        {parsed.status === 'needs_clarification' && (
                          <div className="clarification">
                            <label>
                              Clarification
                              <input
                                value={clarification}
                                onChange={(e) => setClarification(e.target.value)}
                                placeholder="e.g. thickness 5 mm"
                              />
                            </label>
                            <button
                              disabled={!clarification.trim() || busy}
                              onClick={() =>
                                action(async () => {
                                  const combined = `${prompt} ${clarification}`;
                                  setPrompt(combined);
                                  setClarification('');
                                  await parse(combined);
                                })
                              }
                            >
                              Add detail & reinterpret
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                    <details className="sample-library" open={!revision}>
                      <summary>Component templates · 4 families</summary>
                      <div className="sample-grid">
                        {samples.map((sample) => (
                          <button
                            key={sample.family}
                            disabled={running}
                            onClick={() => newDesign(sample)}
                          >
                            <Icon name="cube" />
                            {sample.name}
                            <small>Load example</small>
                          </button>
                        ))}
                      </div>
                    </details>
                    <div className="offline-note">
                      <Icon name="check" />
                      <div>
                        <strong>Local by design.</strong>
                        <p>
                          No API keys. No generated code. Your requirements stay on this machine.
                        </p>
                      </div>
                    </div>
                  </div>
                </section>
                <section className="panel preview-panel" id="studio-model" aria-label="CAD model">
                  <div className="panel-heading">
                    <strong>
                      Parametric preview{' '}
                      <span className="tag">
                        {viewId ? `REV ${viewId.slice(0, 8)}` : 'NO GENERATED MODEL'}
                      </span>
                    </strong>
                    <div className="preview-meta">
                      <span>UNITS</span>
                      <strong>mm</strong>
                    </div>
                  </div>
                  <Suspense fallback={<div className="viewer-loading">Loading 3D renderer…</div>}>
                    <Viewer auth={auth} revisionId={viewId} />
                  </Suspense>
                  <div className="preview-footer">
                    <span>
                      <i />{' '}
                      {viewId
                        ? `Viewing generated revision ${viewId.slice(0, 8)}`
                        : 'Preview appears after confirmation and geometric validation'}
                    </span>
                    <span>
                      {validation?.solid_count
                        ? `${validation.solid_count} solid${validation.solid_count > 1 ? 's' : ''}`
                        : 'B-rep → mesh'}
                    </span>
                  </div>
                </section>
                {draft && (
                  <section
                    className="panel parameters-panel"
                    id="studio-parameters"
                    aria-label="Parameter inspector"
                  >
                    <div className="panel-heading">
                      <strong>Parameters</strong>
                      <span className="tag">{draft.part_family.toUpperCase()} · mm</span>
                    </div>
                    <div className="parameters-body">
                      {parsed?.status === 'ready' && (
                        <p className="interpretation-ready" role="status">
                          Interpretation ready for review
                        </p>
                      )}
                      <div className="parameters-grid">
                        {Object.entries(draft.parameters).map(([key, value]) => (
                          <ParameterField
                            key={key}
                            name={key}
                            value={value}
                            disabled={running}
                            onChange={(value) => editParameter(key, value)}
                          />
                        ))}
                      </div>
                      <details>
                        <summary>Explicit hole positions & complete source JSON</summary>
                        <p id="json-help">
                          Positions are [x,y] from the lower-left face origin; upright uses [y,z].
                          No arbitrary code is accepted.
                        </p>
                        <textarea
                          className="json-editor"
                          aria-label="Structured specification JSON"
                          disabled={running}
                          aria-invalid={!!editorError}
                          aria-describedby={editorError ? 'json-error' : 'json-help'}
                          value={editor}
                          onChange={(e) => editJSON(e.target.value)}
                          spellCheck={false}
                        />
                      </details>
                      {editorError && (
                        <p className="inline-error" id="json-error" role="alert">
                          {editorError}
                        </p>
                      )}
                      {parsed?.diff && parsed.diff.length > 0 && (
                        <div className="diff">
                          <h3>Review the changes</h3>
                          {parsed.diff.map((d, i) => (
                            <div key={i}>
                              <code>{d.path}</code>
                              <span className="before">{JSON.stringify(d.before)}</span>
                              <span>→</span>
                              <strong>{JSON.stringify(d.after)}</strong>
                            </div>
                          ))}
                        </div>
                      )}
                      {parsed?.source_attribution && parsed.source_attribution.length > 0 && (
                        <details>
                          <summary>Where the interpretation came from</summary>
                          <div className="provenance">
                            {parsed.source_attribution.map((source, i) => (
                              <div key={i}>
                                <code>{source.field}</code>
                                <q>{source.source}</q>
                                <span>{source.confidence}</span>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                      <div className="assumptions">
                        <strong>Confirm the interpretation</strong>
                        <ul>
                          {draft.assumptions?.map((a, i) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ul>
                        <p>
                          Structural loads, material suitability, fastener fit, and manufacturing
                          tolerances remain unvalidated.
                        </p>
                        <label className="checkbox">
                          <input
                            type="checkbox"
                            checked={confirmed}
                            onChange={(e) => setConfirmed(e.target.checked)}
                          />
                          I reviewed dimensions, hole positions, optional defaults, and limitations.
                        </label>
                      </div>
                      <div className="generation-row">
                        <div
                          className={`build-feedback ${job?.state === 'failed' ? 'failed' : ''}`}
                          role="status"
                        >
                          <strong>{buildLabel}</strong>
                          <span>
                            {running
                              ? 'One local worker · bounded and cancellable'
                              : job?.state === 'failed'
                                ? `${job.error_code}. The confirmed source is retained. Retry the same geometry or review parameters.`
                                : job?.state === 'cancelled'
                                  ? 'No successful geometry is claimed for this cancelled job.'
                                  : draftChanged
                                    ? 'Review this draft before creating a new revision.'
                                    : job?.state === 'completed'
                                      ? `STEP/STL readback passed for ${viewId?.slice(0, 8) ?? 'the displayed revision'}.`
                                      : 'Geometry is built only after you confirm this source.'}
                          </span>
                        </div>
                        <div className="button-row">
                          {parsed && revision && draftChanged && !running && (
                            <button onClick={() => action(() => selectRevision(revision.id))}>
                              Discard proposed changes
                            </button>
                          )}
                          {revision &&
                            !draftChanged &&
                            (job?.state === 'failed' || job?.state === 'cancelled') && (
                              <button
                                onClick={() =>
                                  action(async () =>
                                    setJob(
                                      await api<Job>(
                                        `/revisions/${revision.id}/generate`,
                                        auth,
                                        {},
                                      ),
                                    ),
                                  )
                                }
                              >
                                Retry geometry
                              </button>
                            )}
                          <button
                            disabled={!auth || busy || !!editorError}
                            onClick={() =>
                              action(async () => {
                                setValidation(
                                  await api<Validation>('/validate', auth, JSON.parse(editor)),
                                );
                                setConstraintsSignature(specKey(JSON.parse(editor)));
                              })
                            }
                          >
                            Check constraints
                          </button>
                          {running ? (
                            <button
                              onClick={() => action(() => api(`/jobs/${job?.id}/cancel`, auth, {}))}
                            >
                              Cancel generation
                            </button>
                          ) : (
                            <button
                              className="primary"
                              disabled={!auth || busy || !confirmed || !!editorError}
                              onClick={() => action(generate)}
                            >
                              {revision && project?.head_id !== revision.id
                                ? 'Restore as new revision & generate'
                                : 'Confirm & generate'}{' '}
                            </button>
                          )}
                        </div>
                      </div>
                      {validation?.errors?.length ? (
                        <ul className="validation-errors">
                          {validation.errors.map((e, i) => (
                            <li key={i}>
                              <strong>{e.code}</strong> {e.message}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  </section>
                )}
                {!draft && (
                  <section
                    className="panel parameters-panel empty-inspector"
                    id="studio-parameters"
                    aria-label="Parameter inspector"
                  >
                    <div className="panel-heading">
                      <strong>Parameter inspector</strong>
                      <span className="tag">mm</span>
                    </div>
                    <div className="parameters-body">
                      <Icon name="sliders" />
                      <h2>Review before building</h2>
                      <p>
                        Interpret a supported brief to inspect dimensions, hole positions and
                        assumptions here.
                      </p>
                      <button onClick={() => setPane('requirements')}>Open requirements</button>
                    </div>
                  </section>
                )}
              </div>
            </>
          )}
          {tab === 'Revision history' && (
            <section className="panel padded">
              <div className="section-heading">
                <div>
                  <h2>Source revisions</h2>
                  <p>
                    Select an older revision to preview it. Confirming it creates a new latest
                    revision without deleting history.
                  </p>
                </div>
                <span className="tag">{project?.revisions?.length ?? 0} REVISIONS</span>
              </div>
              {project?.revisions?.length ? (
                <div className="revision-list">
                  {project.revisions.map((r, index) => (
                    <article key={r.id}>
                      <span className="revision-number">
                        {String(project.revisions!.length - index).padStart(2, '0')}
                      </span>
                      <div>
                        <strong>
                          {r.spec.part_family} / {r.id.slice(0, 8)}{' '}
                          {r.id === project.head_id && <span className="tag">LATEST</span>}
                        </strong>
                        <p>{r.spec.source_text || 'Confirmed structured specification'}</p>
                        <small>
                          {new Date(r.created_at).toLocaleString()} · {r.diff.length} changed fields
                        </small>
                      </div>
                      <button onClick={() => action(() => selectRevision(r.id))}>
                        Preview revision
                      </button>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="empty">
                  Open a saved project or generate your first confirmed revision.
                </p>
              )}
            </section>
          )}
          {tab === 'Validation' && (
            <section className="panel padded">
              <h2>{geometricEvidence ? 'Geometry validation' : 'Draft constraint check'}</h2>
              {validation ? (
                <>
                  <p className="evidence-scope">
                    {geometricEvidence
                      ? `Generated geometry and export readback for revision ${viewId?.slice(0, 8) ?? revision?.id.slice(0, 8) ?? 'selected'}.`
                      : 'Prebuild parameters only. This does not validate newly generated geometry.'}
                  </p>
                  <div className="validation-summary">
                    <span
                      className={
                        !validationFresh ? 'status-warning' : validation.valid ? 'pass' : 'fail'
                      }
                    >
                      {!validationFresh
                        ? 'CHECK AGAIN AFTER EDITS'
                        : validation.valid
                          ? geometricEvidence
                            ? 'CHECKS PASSED'
                            : 'CONSTRAINTS PASSED'
                          : 'NEEDS CORRECTION'}
                    </span>
                    <span>
                      {validation.bbox_mm?.map((v) => v.toFixed(2)).join(' × ')}{' '}
                      {validation.bbox_mm ? 'mm' : ''}
                    </span>
                    <span>
                      {validation.volume_mm3?.toFixed(2)} {validation.volume_mm3 ? 'mm³' : ''}
                    </span>
                  </div>
                  {!validationFresh && (
                    <Notice tone="warning">
                      These constraint results precede your latest edits. Run Check constraints
                      again before relying on them.
                    </Notice>
                  )}
                  <div className="check-list">
                    {validation.checks.map((c, i) => (
                      <div key={i}>
                        <span>{c.check.replaceAll('_', ' ')}</span>
                        <strong className={c.status === 'pass' ? 'pass' : 'fail'}>
                          {c.status.toUpperCase()}
                        </strong>
                      </div>
                    ))}
                  </div>
                  {validation.errors?.map((e, i) => (
                    <p className="inline-error" key={i}>
                      {e.code}: {e.message}
                    </p>
                  ))}
                  <h3>Unvalidated engineering considerations</h3>
                  <ul className="warnings">
                    {validation.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                  {validation.spec_sha256 && (
                    <div className="hash">
                      <small>REPRODUCIBLE SPEC SHA-256</small>
                      <code>{validation.spec_sha256}</code>
                    </div>
                  )}
                  <p>
                    CadQuery {validation.cadquery_version ?? 'not generated yet'} · template v1.0.0
                  </p>
                </>
              ) : (
                <p className="empty">
                  Interpret or generate a design to view its real validation report.
                </p>
              )}
            </section>
          )}
          {tab === 'Exports' && (
            <section className="panel padded">
              <h2>Download engineering files</h2>
              <p>
                Exports are enabled only for a revision that passed B-rep and file readback checks.
              </p>
              <div className="export-revision">
                <Icon name="cube" />
                <div>
                  <strong>
                    {viewId
                      ? `Geometry revision ${viewId.slice(0, 8)}`
                      : 'No completed geometry selected'}
                  </strong>
                  <p>
                    {draftChanged
                      ? 'Uncommitted draft edits are not included in these files.'
                      : 'Files belong to the identified completed revision.'}
                  </p>
                </div>
              </div>
              <div className="export-grid">
                {[
                  [
                    'step',
                    'STEP model',
                    'Neutral editable B-rep interoperability. Not a native feature tree.',
                  ],
                  [
                    'stl',
                    'STL mesh',
                    'Watertight triangulated preview / printing input; millimeter convention.',
                  ],
                  [
                    'json',
                    'Source specification',
                    'Canonical editable parameters and the original request.',
                  ],
                  [
                    'report',
                    'Validation report',
                    'Geometry checks, environment, spec hash, and open warnings.',
                  ],
                  [
                    'zip',
                    'Complete handoff',
                    'STEP + STL + source + validation + revision history and metadata.',
                  ],
                ].map(([format, title, detail]) => (
                  <article key={format}>
                    <span className="file-icon">
                      <Icon name="download" />
                      {format.toUpperCase()}
                    </span>
                    <h3>{title}</h3>
                    <p>{detail}</p>
                    <button disabled={!auth || !viewId || busy} onClick={() => exportFile(format)}>
                      Download {format.toUpperCase()}
                    </button>
                  </article>
                ))}
              </div>
            </section>
          )}
          {tab === 'Evaluation' && (
            <section className="panel padded">
              <h2>Internal evaluation results</h2>
              <p>
                Authored prompts with fixed development / held-out labels. This is an internal
                constrained-grammar evaluation.
              </p>
              {evaluation?.case_count ? (
                <>
                  <div className="evaluation-metrics">
                    {[
                      ['Cases', evaluation.case_count],
                      [
                        'Normalized outcomes',
                        `${((evaluation.fully_correct_rate ?? 0) * 100).toFixed(1)}%`,
                      ],
                      ['Slot F1', `${((evaluation.slot_f1 ?? 0) * 100).toFixed(1)}%`],
                      [
                        'Clarification precision',
                        `${((evaluation.clarification_precision ?? 0) * 100).toFixed(1)}%`,
                      ],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <small>{label}</small>
                        <strong>{value}</strong>
                      </div>
                    ))}
                  </div>
                  <p>{evaluation.methodology}</p>
                  <div
                    className="table-wrap"
                    role="region"
                    aria-label="Evaluation geometry table"
                    tabIndex={0}
                  >
                    <table>
                      <thead>
                        <tr>
                          <th>Family</th>
                          <th>Geometric checks</th>
                          <th>Generation time</th>
                          <th>Volume</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evaluation.geometry?.map((g, i) => (
                          <tr key={i}>
                            <td>{g.family}</td>
                            <td>{g.valid ? 'PASS' : 'FAIL'}</td>
                            <td>{g.generation_ms?.toFixed(1) ?? 'Failed'} ms</td>
                            <td>{g.volume_mm3.toFixed(1)} mm³</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <button
                    className="report-download"
                    disabled={!auth}
                    onClick={() =>
                      auth &&
                      action(() => download('/evaluation', auth, 'text2cad-evaluation.json'))
                    }
                  >
                    Raw evaluation JSON
                  </button>
                </>
              ) : (
                <p className="empty">
                  No evaluation file found. Run <code>scripts/evaluate.py</code> locally to produce
                  measured results.
                </p>
              )}
            </section>
          )}
          {tab === 'Field guide' && (
            <section className="panel padded guide">
              <h2>Design and revision workflow</h2>
              <ol>
                <li>
                  Choose one of four families. Describe all critical dimensions with explicit units.
                </li>
                <li>
                  Interpret requirements. Resolve any questions; inspect the structured parameters
                  and source spans.
                </li>
                <li>
                  Confirm the parameters and assumptions. Geometry is generated in a bounded local
                  worker.
                </li>
                <li>
                  Orbit the actual STL, review validation evidence, and download STEP/STL or the
                  complete handoff.
                </li>
                <li>
                  Request a change such as “increase thickness to 6 mm.” Review the diff before
                  creating an immutable revision.
                </li>
                <li>
                  Select a previous revision to undo non-destructively. Restore it as a new revision
                  when ready.
                </li>
              </ol>
              <h3>Coordinate frames</h3>
              <p>
                Plate/finger: x = length, y = width, z = thickness. Bracket base holes use [x,y];
                upright holes use [y,z] and cut along x. Enclosure height is the base height; base
                and lid are exported as two solids with a 3 mm display gap.
              </p>
              <h3>Supported text grammar</h3>
              <p>
                Named dimensions or explicit dimension tuples; four-hole centered rectangular
                patterns with count, diameter, and spacing. Use structured JSON for arbitrary
                approved hole positions. Tapped threads, gears, complex organic shapes, and
                arbitrary CAD code are unsupported.
              </p>
              <h3>Engineering limits</h3>
              <p>
                These are constrained parametric models. No structural stress, material suitability,
                specific fastener fit, manufacturing tolerance, or regulatory safety certification
                is performed. Optional local LLM support is not required or installed.
              </p>
            </section>
          )}
          <footer className="page-footer">
            <span>
              TEXT2CAD <span>/</span> PRECISE BY CONSTRUCTION
            </span>
            <span>
              Constrained parametric design. Engineering review required.{' '}
              <button
                disabled={!auth}
                onClick={() => {
                  setAuth(null);
                  setViewId(null);
                  setProjects([]);
                  setProject(null);
                }}
              >
                End session
              </button>
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
