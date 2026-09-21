import { createGravityRenderer, type GravityRenderer } from './gravity-renderer';

export function initGravityHome() {
  const home = document.querySelector<HTMLElement>('[data-gravity]');
  const canvas = document.querySelector<HTMLCanvasElement>('[data-gravity-canvas]');
  const archive = document.querySelector<HTMLElement>('[data-archive]');
  const enter = document.querySelector<HTMLButtonElement>('[data-enter]');
  const replay = document.querySelector<HTMLButtonElement>('[data-replay]');
  const status = document.querySelector<HTMLElement>('[data-gravity-status]');
  if (!home || !canvas || !archive || !enter || !replay) return;

  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const DURATION = 2200;
  let state: 'flowing' | 'settling' | 'still' = 'flowing';
  let renderer: GravityRenderer | null = null;
  let frame = 0;
  let last = performance.now();
  let elapsed = 0;
  let sceneTime = 0;
  let rest = 0;
  let keyboardEntry = false;
  let active = true;
  let resumeTime = 0;

  function draw() { renderer?.render(sceneTime, rest); }
  function schedule() {
    if (frame || document.hidden || !active || state === 'still') return;
    if (motion.matches && state === 'flowing') return;
    last = performance.now();
    frame = requestAnimationFrame(tick);
  }
  function tick(now: number) {
    frame = 0;
    const delta = Math.min(now - last, 64);
    last = now;
    let velocity = 1;
    if (state === 'settling') {
      elapsed = Math.min(elapsed + delta, DURATION);
      const p = elapsed / DURATION;
      velocity = Math.pow(1 - p, 3);
      rest = p * p * p * (p * (p * 6 - 15) + 10);
    } else {
      resumeTime = Math.min(resumeTime + delta, 900);
      rest *= Math.exp(-delta / 220);
      velocity = Math.min(1, resumeTime / 900);
    }
    if (!motion.matches) sceneTime += delta * .001 * velocity;
    draw();
    if (state === 'settling' && elapsed >= DURATION) {
      finish();
      return;
    }
    if (!document.hidden && state !== 'still' && active) frame = requestAnimationFrame(tick);
  }
  function finish() {
    state = 'still';
    home!.dataset.state = state;
    archive!.inert = false;
    if (status) status.textContent = '时间已静止。博客、项目与摄影入口已展开。';
    if (keyboardEntry) archive!.querySelector<HTMLAnchorElement>('a')?.focus({ preventScroll: true });
  }
  function reveal(keyboard = false) {
    if (state !== 'flowing') return;
    keyboardEntry = keyboard;
    state = 'settling';
    elapsed = 0;
    enter!.inert = true;
    home!.dataset.state = state;
    if (motion.matches) {
      rest = 1;
      draw();
      finish();
    } else schedule();
  }
  function resume() {
    state = 'flowing';
    home!.dataset.state = state;
    archive!.inert = true;
    enter!.inert = false;
    resumeTime = 0;
    if (status) status.textContent = '时间继续流动。';
    enter!.focus({ preventScroll: true });
    schedule();
  }
  enter.addEventListener('click', event => reveal(event.detail === 0));
  replay.addEventListener('click', resume);
  home.addEventListener('wheel', event => { if (Math.abs(event.deltaY) > 3) reveal(); }, { passive: true });
  let startY = 0;
  home.addEventListener('touchstart', event => { startY = event.touches[0].clientY; }, { passive: true });
  home.addEventListener('touchmove', event => {
    if (Math.abs(event.touches[0].clientY - startY) > 24) reveal();
  }, { passive: true });
  home.addEventListener('keydown', event => {
    if (state === 'flowing' && ['ArrowDown', 'PageDown'].includes(event.key)) {
      event.preventDefault();
      reveal(true);
    }
  });
  window.addEventListener('resize', () => { renderer?.resize(); draw(); });
  document.addEventListener('visibilitychange', () => {
    cancelAnimationFrame(frame);
    frame = 0;
    schedule();
  });
  motion.addEventListener('change', () => {
    cancelAnimationFrame(frame);
    frame = 0;
    if (motion.matches && state === 'settling') { rest = 1; draw(); finish(); }
    else schedule();
  });
  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault();
    home.dataset.renderer = 'poster';
    renderer = null;
  });
  async function loadRenderer() {
    try {
      const next = await createGravityRenderer(canvas!);
      if (!active) { next?.dispose(); return; }
      renderer = next;
      draw();
      home!.dataset.renderer = next ? 'webgl' : 'poster';
      schedule();
    } catch (error) {
      // The full-quality poster and all navigation remain usable without WebGL.
      home!.dataset.renderer = 'poster';
      console.warn('Gravity scene uses its static fallback:', error);
    }
  }
  canvas.addEventListener('webglcontextrestored', loadRenderer);
  window.addEventListener('pagehide', () => { active = false; cancelAnimationFrame(frame); frame = 0; });
  window.addEventListener('pageshow', () => { active = true; schedule(); });
  void loadRenderer();
}
