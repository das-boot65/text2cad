import { useState, type ReactNode } from 'react';
import type { Project } from './api';
type IconName =
  | 'cube'
  | 'history'
  | 'check'
  | 'download'
  | 'chart'
  | 'help'
  | 'plus'
  | 'menu'
  | 'close'
  | 'sun'
  | 'moon'
  | 'sliders'
  | 'edit'
  | 'fit'
  | 'wire'
  | 'zoomIn'
  | 'zoomOut'
  | 'front'
  | 'top'
  | 'rotate';
const paths: Record<IconName, ReactNode> = {
  cube: (
    <>
      <path d="m12 3 9 5v9l-9 5-9-5V8zM3 8l9 5 9-5M12 13v9M7 5.8l9 5" />
    </>
  ),
  history: (
    <>
      <path d="M3 10a9 9 0 1 1 1 7M3 3v7h7M12 7v6l4 2" />
    </>
  ),
  check: (
    <>
      <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6" />
    </>
  ),
  download: <path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4" />,
  chart: <path d="M4 3v17h17M8 15v-4M13 15V7M18 15V4" />,
  help: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4M12 17h.01" />
    </>
  ),
  plus: <path d="M12 4v16M4 12h16" />,
  menu: <path d="M3 6h18M3 12h18M3 18h18" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 1v2M12 21v2M1 12h2M21 12h2M4 4l2 2M18 18l2 2M4 20l2-2M18 6l2-2" />
    </>
  ),
  moon: <path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z" />,
  sliders: (
    <>
      <path d="M3 6h8M15 6h6M3 12h2M9 12h12M3 18h12M19 18h2" />
      <circle cx="13" cy="6" r="2" />
      <circle cx="7" cy="12" r="2" />
      <circle cx="17" cy="18" r="2" />
    </>
  ),
  edit: (
    <>
      <path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14z" />
    </>
  ),
  fit: <path d="M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6" />,
  wire: (
    <>
      <rect x="4" y="4" width="16" height="16" />
      <path d="m4 4 16 16M4 20 20 4M12 4v16M4 12h16" />
    </>
  ),
  zoomIn: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="m15 15 6 6M6 10h8M10 6v8" />
    </>
  ),
  zoomOut: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="m15 15 6 6M6 10h8" />
    </>
  ),
  front: (
    <>
      <rect x="4" y="6" width="16" height="12" />
      <path d="M8 10h8M8 14h8" />
    </>
  ),
  top: (
    <>
      <path d="m12 3 10 9-10 9L2 12zM12 7v10M6 12h12" />
    </>
  ),
  rotate: (
    <>
      <path d="M20 8a9 9 0 1 0 1 7M20 2v6h-6" />
    </>
  ),
};
export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      className="icon"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
export function Status({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'good' | 'warning' | 'danger';
}) {
  return (
    <span className={`status status-${tone}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}
export function Notice({
  children,
  tone = 'info',
  onDismiss,
}: {
  children: ReactNode;
  tone?: 'info' | 'error' | 'warning';
  onDismiss?: () => void;
}) {
  return (
    <div className={`alert ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon name={tone === 'error' || tone === 'warning' ? 'help' : 'check'} />
      <div>{children}</div>
      {onDismiss && (
        <button
          className="icon-button"
          aria-label={tone === 'error' ? 'Dismiss error' : 'Dismiss notification'}
          onClick={onDismiss}
        >
          <Icon name="close" />
        </button>
      )}
    </div>
  );
}
const navIcons: IconName[] = ['cube', 'history', 'check', 'download', 'chart', 'help'];
export function StudioNav({
  tabs,
  active,
  onSelect,
  onNew,
  projects,
  selectedProject,
  onProject,
  dark,
  onTheme,
  connected,
}: {
  tabs: string[];
  active: string;
  onSelect: (name: string) => void;
  onNew: () => void;
  projects: Project[];
  selectedProject: string | null;
  onProject: (id: string) => void;
  dark: boolean;
  onTheme: () => void;
  connected: boolean;
}) {
  const [open, setOpen] = useState(false);
  const close = (action: () => void) => {
    action();
    setOpen(false);
  };
  return (
    <aside className={`sidebar ${open ? 'is-open' : ''}`}>
      <button className="brand" onClick={() => close(() => onSelect('Design studio'))}>
        <Icon name="cube" />
        <span>
          Text<span className="brand-light">2</span>CAD
        </span>
      </button>
      <button
        className="menu-toggle"
        aria-label="Toggle project navigation"
        aria-expanded={open}
        aria-controls="studio-navigation"
        onClick={() => setOpen(!open)}
      >
        <Icon name={open ? 'close' : 'menu'} />
        Projects & tools
      </button>
      <div className="nav-body" id="studio-navigation">
        <button className="new-project" onClick={() => close(onNew)}>
          <Icon name="plus" />
          New design
        </button>
        <nav aria-label="Workspace">
          {tabs.map((name, index) => (
            <button
              key={name}
              className={`nav-item ${active === name ? 'active' : ''}`}
              aria-current={active === name ? 'page' : undefined}
              onClick={() => close(() => onSelect(name))}
            >
              <Icon name={navIcons[index]} />
              <span>{name}</span>
            </button>
          ))}
        </nav>
        <div className="nav-label projects-label">
          Recent designs <span>{projects.length}</span>
        </div>
        <div className="project-list">
          {projects.length ? (
            projects.slice(0, 8).map((project) => (
              <button
                key={project.id}
                title={project.name}
                className={selectedProject === project.id ? 'selected' : ''}
                onClick={() => close(() => onProject(project.id))}
              >
                <Icon name="cube" />
                <span>
                  {project.name}
                  <small>{new Date(project.created_at).toLocaleDateString()}</small>
                </span>
              </button>
            ))
          ) : (
            <p>Confirmed designs appear here.</p>
          )}
        </div>
        <div className="sidebar-bottom">
          <button className="theme-switch" onClick={onTheme}>
            <Icon name={dark ? 'sun' : 'moon'} />
            {dark ? 'Light' : 'Dark'} appearance
          </button>
          <Status>{connected ? 'Local session active' : 'Sign in to design'}</Status>
          <p>Offline parser · Native CAD</p>
        </div>
      </div>
    </aside>
  );
}
export function ParameterField({
  name,
  value,
  disabled,
  onChange,
}: {
  name: string;
  value: number | string;
  disabled: boolean;
  onChange: (value: number | string) => void;
}) {
  return (
    <label className="parameter-field">
      <span>{name.replace('_mm', '').replaceAll('_', ' ')}</span>
      {typeof value === 'number' ? (
        <div className="unit-input">
          <input
            type="number"
            aria-label={name}
            step="any"
            value={value}
            disabled={disabled}
            onChange={(event) => onChange(Number(event.target.value))}
          />
          <span>mm</span>
        </div>
      ) : (
        <select
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="flat">Flat</option>
          <option value="tapered">Tapered</option>
        </select>
      )}
    </label>
  );
}
