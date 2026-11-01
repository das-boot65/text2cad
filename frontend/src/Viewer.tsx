import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import type { Auth } from './api';
import { Icon } from './ui';

export function Viewer({ auth, revisionId }: { auth: Auth | null; revisionId: string | null }) {
  const mount = useRef<HTMLDivElement>(null);
  const reset = useRef<() => void>(() => {});
  const wire = useRef<() => void>(() => {});
  const zoom = useRef<(factor: number) => void>(() => {});
  const preset = useRef<(view: 'front' | 'top' | 'isometric') => void>(() => {});
  const orbit = useRef<(horizontal: number, vertical: number) => void>(() => {});
  const [wireframe, setWireframe] = useState(false);
  const [status, setStatus] = useState('No validated model yet');
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const host = mount.current;
    if (!host || !auth || !revisionId) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      setStatus('3D rendering is unavailable. STEP/STL downloads remain available.');
      setFailed(true);
      return;
    }
    const abort = new AbortController();
    let disposed = false;
    let frame = 0;
    let needsRender = true;
    setStatus('Loading validated STL…');
    setFailed(false);
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    const token = (name: string) => getComputedStyle(host).getPropertyValue(name).trim();
    renderer.setClearColor(token('--viewer-bg'));
    host.appendChild(renderer.domElement);
    renderer.domElement.setAttribute(
      'aria-label',
      'Interactive 3D model; drag to orbit, arrow keys to pan, plus or minus to zoom',
    );
    renderer.domElement.setAttribute('role', 'img');
    renderer.domElement.tabIndex = 0;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 10000);
    camera.position.set(100, 80, 110);
    const controls = new OrbitControls(camera, renderer.domElement);
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    controls.enableDamping = !reducedMotion.matches;
    controls.listenToKeyEvents(renderer.domElement);
    const motionChanged = () => {
      controls.enableDamping = !reducedMotion.matches;
      invalidate();
    };
    reducedMotion.addEventListener('change', motionChanged);
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === '+' || event.key === '=') {
        event.preventDefault();
        zoom.current(0.85);
      }
      if (event.key === '-') {
        event.preventDefault();
        zoom.current(1.18);
      }
      if (event.key === '0') {
        event.preventDefault();
        reset.current();
      }
    };
    renderer.domElement.addEventListener('keydown', keyboard);
    let modelMaterial: THREE.MeshStandardMaterial | null = null;
    let edgeMaterial: THREE.LineBasicMaterial | null = null;
    let liveGrid: THREE.GridHelper | null = null;
    const applyTheme = () => {
      renderer.setClearColor(token('--viewer-bg'));
      modelMaterial?.color.set(token('--viewer-model'));
      edgeMaterial?.color.set(token('--viewer-edge'));
      if (liveGrid) {
        const positions = liveGrid.geometry.getAttribute('position');
        const colors = liveGrid.geometry.getAttribute('color');
        const minor = new THREE.Color(token('--viewer-grid'));
        const major = new THREE.Color(token('--viewer-grid-major'));
        for (let i = 0; i < positions.count; i += 2) {
          const axis =
            (positions.getX(i) === 0 && positions.getX(i + 1) === 0) ||
            (positions.getZ(i) === 0 && positions.getZ(i + 1) === 0);
          const color = axis ? major : minor;
          colors.setXYZ(i, color.r, color.g, color.b);
          colors.setXYZ(i + 1, color.r, color.g, color.b);
        }
        colors.needsUpdate = true;
      }
      invalidate();
    };
    const themeObserver = new MutationObserver(applyTheme);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
    scene.add(new THREE.HemisphereLight(0xffffff, 0x718796, 2.8));
    const light = new THREE.DirectionalLight(0xffffff, 3);
    light.position.set(60, 100, 40);
    scene.add(light);
    const fill = new THREE.DirectionalLight(0x9cbbd8, 1.3);
    fill.position.set(-60, 30, -40);
    scene.add(fill);
    const geometries: THREE.BufferGeometry[] = [];
    const materials: THREE.Material[] = [];
    const resize = () => {
      const width = host.clientWidth,
        height = host.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / Math.max(1, height);
      camera.updateProjectionMatrix();
      invalidate();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();
    function invalidate() {
      needsRender = true;
      if (!frame && !disposed) frame = requestAnimationFrame(draw);
    }
    function draw() {
      if (disposed) return;
      const changed = controls.update();
      if ((needsRender || changed) && host!.clientWidth && host!.clientHeight)
        renderer.render(scene, camera);
      needsRender = false;
      frame = 0;
      if (changed) invalidate();
    }
    controls.addEventListener('change', invalidate);
    invalidate();
    fetch(`/api/revisions/${revisionId}/downloads/stl`, {
      headers: { Authorization: `Bearer ${auth.token}` },
      signal: abort.signal,
    })
      .then((r) => {
        if (!r.ok) throw Error('Validated preview could not be loaded.');
        return r.arrayBuffer();
      })
      .then((buffer) => {
        if (disposed) return;
        const geometry = new STLLoader().parse(buffer);
        geometry.computeVertexNormals();
        geometry.computeBoundingBox();
        const size = new THREE.Vector3();
        geometry.boundingBox!.getSize(size);
        geometry.center();
        geometries.push(geometry);
        const material = new THREE.MeshStandardMaterial({
          color: token('--viewer-model'),
          metalness: 0.35,
          roughness: 0.38,
        });
        modelMaterial = material;
        materials.push(material);
        const mesh = new THREE.Mesh(geometry, material);
        mesh.rotation.x = -Math.PI / 2;
        scene.add(mesh);
        const edges = new THREE.EdgesGeometry(geometry, 28);
        geometries.push(edges);
        const lineMaterial = new THREE.LineBasicMaterial({
          color: token('--viewer-edge'),
          transparent: true,
          opacity: 0.5,
        });
        edgeMaterial = lineMaterial;
        materials.push(lineMaterial);
        const outline = new THREE.LineSegments(edges, lineMaterial);
        outline.rotation.x = -Math.PI / 2;
        scene.add(outline);
        const largest = Math.max(size.x, size.y, size.z, 10);
        const grid = new THREE.GridHelper(
          largest * 2.6,
          26,
          token('--viewer-grid-major'),
          token('--viewer-grid'),
        );
        liveGrid = grid;
        grid.position.y = -size.z / 2 - 0.3;
        scene.add(grid);
        geometries.push(grid.geometry);
        if (Array.isArray(grid.material)) materials.push(...grid.material);
        else materials.push(grid.material);
        reset.current = () => {
          camera.up.set(0, 1, 0);
          camera.position.set(largest * 1.15, largest * 0.95, largest * 1.3);
          camera.near = 0.1;
          camera.far = largest * 100;
          camera.updateProjectionMatrix();
          controls.target.set(0, 0, 0);
          controls.update();
        };
        reset.current();
        wire.current = () => {
          material.wireframe = !material.wireframe;
          setWireframe(material.wireframe);
          invalidate();
        };
        setWireframe(false);
        zoom.current = (factor) => {
          camera.position.sub(controls.target).multiplyScalar(factor).add(controls.target);
          controls.update();
        };
        preset.current = (view) => {
          if (view === 'isometric') return reset.current();
          controls.target.set(0, 0, 0);
          camera.up.set(0, view === 'top' ? 0 : 1, view === 'top' ? -1 : 0);
          camera.position.set(
            0,
            view === 'top' ? largest * 2 : 0,
            view === 'top' ? 0.001 : largest * 2,
          );
          controls.update();
        };
        orbit.current = (horizontal, vertical) => {
          const offset = camera.position.clone().sub(controls.target);
          const spherical = new THREE.Spherical().setFromVector3(offset);
          spherical.theta += horizontal;
          spherical.phi = Math.max(0.05, Math.min(Math.PI - 0.05, spherical.phi + vertical));
          camera.position.copy(
            new THREE.Vector3().setFromSpherical(spherical).add(controls.target),
          );
          controls.update();
        };
        invalidate();
        setStatus('Validated STL · dimensions in mm');
      })
      .catch((e) => {
        if (!disposed && e.name !== 'AbortError') {
          setStatus(e.message);
          setFailed(true);
        }
      });
    return () => {
      disposed = true;
      abort.abort();
      cancelAnimationFrame(frame);
      observer.disconnect();
      themeObserver.disconnect();
      reducedMotion.removeEventListener('change', motionChanged);
      renderer.domElement.removeEventListener('keydown', keyboard);
      controls.removeEventListener('change', invalidate);
      controls.dispose();
      geometries.forEach((g) => g.dispose());
      materials.forEach((m) => m.dispose());
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      reset.current = () => {};
      wire.current = () => {};
      zoom.current = () => {};
      preset.current = () => {};
      orbit.current = () => {};
    };
  }, [auth, revisionId, retry]);
  return (
    <div className="viewer-shell">
      <div className="viewer" ref={mount} />
      {!revisionId && (
        <div className="viewer-empty">
          <Icon name="cube" />
          <h3>No generated model</h3>
          <p>
            Open Requirements to describe a part, then review its parameters and confirm a build.
          </p>
        </div>
      )}
      <div className={`viewer-status ${failed ? 'failed' : ''}`} role="status">
        <i />
        {revisionId ? status : 'No validated model yet'}
        {failed && <button onClick={() => setRetry(retry + 1)}>Retry</button>}
      </div>
      <div className="viewer-toolbar">
        <button disabled={!revisionId} onClick={() => reset.current()}>
          <Icon name="fit" />
          Reset view
        </button>
        <button
          className="icon-button"
          aria-label="Zoom in"
          title="Zoom in"
          disabled={!revisionId}
          onClick={() => zoom.current(0.85)}
        >
          <Icon name="zoomIn" />
        </button>
        <button
          className="icon-button"
          aria-label="Zoom out"
          title="Zoom out"
          disabled={!revisionId}
          onClick={() => zoom.current(1.18)}
        >
          <Icon name="zoomOut" />
        </button>
        <details className="camera-menu">
          <summary>
            <Icon name="rotate" />
            Camera
          </summary>
          <div className="camera-options" role="group" aria-label="Camera controls">
            <button disabled={!revisionId} onClick={() => preset.current('front')}>
              <Icon name="front" />
              Front view
            </button>
            <button disabled={!revisionId} onClick={() => preset.current('top')}>
              <Icon name="top" />
              Top view
            </button>
            <button disabled={!revisionId} onClick={() => preset.current('isometric')}>
              <Icon name="cube" />
              Isometric view
            </button>
            <button disabled={!revisionId} onClick={() => orbit.current(-0.25, 0)}>
              Orbit left
            </button>
            <button disabled={!revisionId} onClick={() => orbit.current(0.25, 0)}>
              Orbit right
            </button>
            <button disabled={!revisionId} onClick={() => orbit.current(0, -0.25)}>
              Orbit up
            </button>
            <button disabled={!revisionId} onClick={() => orbit.current(0, 0.25)}>
              Orbit down
            </button>
          </div>
        </details>
        <button disabled={!revisionId} aria-pressed={wireframe} onClick={() => wire.current()}>
          <Icon name="wire" />
          Wireframe
        </button>
      </div>
      <div className="axis">
        <span>X</span>
        <span>Y</span>
        <span>Z ↑</span>
      </div>
      <div className="viewer-help">
        Drag to orbit <span>·</span> Right-drag to pan <span>·</span> Arrow keys pan <span>·</span>{' '}
        + / − zoom
      </div>
    </div>
  );
}
