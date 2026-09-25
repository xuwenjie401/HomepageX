/** A curved-ray view of a three-dimensional accretion plane.
 * Material follows differential orbits with slow inward drift; the camera stays anchored.
 * The controller owns time so entry, replay and reduced motion share one clock.
 */
const vertexSource = `
attribute vec2 a_position;
varying vec2 v_uv;
void main() {
  v_uv = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}`;

const fragmentSource = `
precision highp float;
uniform sampler2D u_formulas;
uniform vec2 u_resolution;
uniform vec2 u_pointer;
uniform float u_time;
uniform float u_rest;
varying vec2 v_uv;
const float TAU = 6.28318530718;

float hash(vec2 p) {
  vec3 q = fract(vec3(p.xyx) * 0.1031);
  q += dot(q, q.yzx + 33.33);
  return fract((q.x + q.y) * q.z);
}
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x),
    mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
vec3 stars(vec2 p) {
  vec3 color = vec3(0.0);
  for (int layer = 0; layer < 2; layer++) {
    float scale = 165.0 + float(layer) * 98.0;
    vec2 cell = floor(p * scale);
    vec2 local = fract(p * scale) - vec2(hash(cell), hash(cell + 19.7));
    float seed = hash(cell + 37.1);
    float star = exp(-dot(local, local) * (90.0 + seed * 260.0));
    star += exp(-length(local) * 22.0) * step(0.997, seed) * 0.22;
    float bright = step(0.972, seed) * (0.22 + pow(seed, 32.0));
    color += mix(vec3(0.57, 0.70, 0.82), vec3(1.0, 0.85, 0.61), hash(cell + 5.0)) * star * bright;
  }
  return color;
}

// A shallow warp keeps the observer within the extended disk, just above its
// material surface. The same surface carries plasma, filaments and equations.
float sheetHeight(vec3 point) {
  float r = length(point.xz);
  if (r < 3.8) return 0.0;
  float angle = atan(point.z, point.x);
  return smoothstep(3.8, 12.0, r) * (r - 3.8) * 0.024 * sin(angle * 2.0 + log(r));
}

// Short, overlapping material lifetimes bound differential shear. Both samples
// travel in the same direction; their weights vanish before either phase wraps.
float materialDensity(float r, float angle, float phase) {
  const float radialDrift = 0.002;
  float inward = log(r) + phase * radialDrift;
  float angularSpeed = 0.36 * pow(5.0 / r, 1.2);
  // Integrate the orbital speed along the very slow inward trajectory. Azimuthal
  // transport dominates: the material orbits many times before drifting inward.
  float angularTravel = angularSpeed * (1.0 - exp(-1.2 * radialDrift * phase)) / (1.2 * radialDrift);
  float orbit = angle - angularTravel - 3.8 * pow(r, -0.65);
  vec2 circular = vec2(cos(orbit), sin(orbit));
  float turbulence = noise(circular * 9.0 + inward * 7.0);
  float fine = noise(vec2(inward * 80.0 + turbulence * 1.8, 0.0) + circular * 2.4);
  float threads = smoothstep(0.48, 0.91, noise(vec2(inward * 175.0, 2.0) + circular * 4.0));
  float clumps = noise(circular * 13.0 + inward * 18.0);

  // Equations and light share this exact velocity field and material phase.
  // Their emissivity fades into the hot inner filaments instead of floating
  // over the disk as an independently moving texture.
  float legibility = smoothstep(1.7, 6.0, r);
  vec2 inkUv = vec2(-orbit / TAU * 5.0, -inward * 0.9);
  inkUv.x += turbulence * 0.006 * (1.0 - legibility);
  float ink = texture2D(u_formulas, fract(inkUv)).r;
  float wake = texture2D(u_formulas, fract(inkUv - vec2(0.006, 0.0))).r;
  float glyphs = (ink * (0.22 + legibility * 1.35) + wake * 0.16) * (0.45 + clumps * 0.75);
  float gas = (0.12 + fine * 0.62 + threads * 0.34) * (0.55 + clumps * 0.7);
  return gas + glyphs;
}

vec3 disk(vec3 point) {
  float r = length(point.xz);
  float angle = atan(point.z, point.x);
  float phaseA = mod(u_time + 10.0, 20.0) - 10.0;
  float phaseB = mod(u_time + 20.0, 20.0) - 10.0;
  float blend = 0.5 + 0.5 * cos(phaseA * TAU / 20.0);
  float gas = materialDensity(r, angle, phaseA) * blend
    + materialDensity(r, angle, phaseB) * (1.0 - blend);
  float inner = smoothstep(1.32, 1.72, r);
  float heat = 0.82 * exp(-(r - 1.65) * 0.55) + 0.30 * pow(2.0 / max(r, 2.0), 0.6);
  float edge = 1.0 - smoothstep(18.0, 28.0, r);
  float approaching = 0.75 + 0.55 * smoothstep(-1.0, 1.0, cos(angle + 0.6));
  vec3 gold = mix(vec3(0.60, 0.32, 0.105), vec3(1.0, 0.72, 0.37), min(heat * 1.3, 1.0));
  gold = mix(gold, vec3(1.0, 0.95, 0.81), pow(min(heat, 1.0), 3.0) * 0.70);
  return gold * gas * heat * inner * edge * approaching * 3.6;
}

void main() {
  float aspect = u_resolution.x / u_resolution.y;
  vec2 center = vec2(0.535, 0.58);
  // Keep the horizon whole on narrow displays, with space for the archive below.
  if (aspect < 1.0) center = vec2(0.5, 0.66);
  vec2 p = (v_uv - center) * vec2(aspect, 1.0) * 2.0;
  float framing = mix(1.30, 1.0, smoothstep(0.45, 1.1, aspect));
  p *= framing * (1.0 - u_rest * 0.018);
  float roll = 0.16;
  p = mat2(cos(roll), -sin(roll), sin(roll), cos(roll)) * p;
  // The camera sits inside the disk's outer radius, looking almost along it.
  vec3 eye = vec3(u_pointer.x * 0.18, 0.72 + u_pointer.y * 0.06, 10.5);
  vec3 forward = normalize(-eye);
  vec3 right = normalize(cross(forward, vec3(0, 1, 0)));
  vec3 up = cross(right, forward);
  vec3 direction = normalize(forward * 1.45 + right * p.x + up * p.y);
  vec3 position = eye;
  float momentum = dot(cross(position, direction), cross(position, direction));
  vec3 light = vec3(0.0);
  float transmission = 1.0;
  float captured = 0.0;

  // Integrate a central gravitational field. Rays crossing the disk on its far
  // side curve above and below the shadow, forming the secondary lensed image.
  for (int i = 0; i < 112; i++) {
    float radius = length(position);
    if (radius < 1.0) { captured = 1.0; break; }
    if (radius > 32.0) break;
    float stepLength = clamp(radius * 0.115, 0.045, 0.8);
    float radius2 = radius * radius;
    vec3 acceleration = -1.5 * momentum * position / (radius2 * radius2 * radius);
    vec3 next = position + direction * stepLength + 0.5 * acceleration * stepLength * stepLength;
    direction += acceleration * stepLength;
    float heightBefore = position.y;
    if (abs(position.y) < 1.4 || abs(next.y) < 1.4) {
      heightBefore -= sheetHeight(position);
      float heightAfter = next.y - sheetHeight(next);
      if (heightBefore * heightAfter < 0.0) {
        vec3 hit = mix(position, next, heightBefore / (heightBefore - heightAfter));
        float r = length(hit.xz);
        if (r > 1.32) {
          light += disk(hit) * transmission;
          transmission *= mix(0.38, 0.78, smoothstep(3.0, 14.0, r));
        }
      }
    }
    // A thin volume around the hot inner disk softens the light without
    // blurring the opaque event horizon or the finely resolved filaments.
    float planeRadius = length(position.xz);
    if (planeRadius < 24.0 && abs(heightBefore) < 0.7) {
      float haze = exp(-abs(heightBefore) / (0.045 + planeRadius * 0.006))
        * pow(2.0 / max(planeRadius, 2.0), 1.1);
      light += vec3(1.0, 0.58, 0.23) * haze * stepLength * 0.10 * transmission;
    }
    position = next;
  }
  vec2 sky = vec2(atan(direction.x, -direction.z), asin(clamp(normalize(direction).y, -1.0, 1.0)));
  vec3 background = stars(sky) + vec3(0.0025, 0.003, 0.0045);
  // A restrained photon glow traces the boundary instead of filling the void.
  float impact = sqrt(momentum);
  float photon = exp(-abs(impact - 2.598) * 75.0);
  light += vec3(1.0, 0.76, 0.43) * photon * 0.30;
  vec3 color = light + background * (1.0 - captured) * transmission;
  color = 1.0 - exp(-color * 1.30);
  color = pow(color, vec3(0.88));
  float vignette = 1.0 - smoothstep(0.35, 1.6, length((v_uv - 0.5) * vec2(aspect * 0.6, 1.0)));
  color *= 0.78 + vignette * 0.22;
  gl_FragColor = vec4(color, 1.0);
}`;

export interface GravityRenderer {
  render: (time: number, rest: number) => void;
  resize: () => void;
  setPointer: (x: number, y: number) => void;
  dispose: () => void;
}

/** Local, power-of-two glyph atlas; no font downloads or extra runtime library. */
function createFormulaAtlas() {
  const atlas = document.createElement('canvas');
  atlas.width = 1024;
  atlas.height = 1024;
  const context = atlas.getContext('2d');
  if (!context) throw new Error('Cannot create formula atlas');
  context.fillStyle = '#000';
  context.fillRect(0, 0, 1024, 1024);
  context.textBaseline = 'middle';
  const formulas = [
    'Gμν + Λgμν = 8πG Tμν', 'E = mc²', 'iℏ ∂ψ/∂t = Ĥψ',
    'ds² = −c²dt² + dx²', '∇ · E = ρ/ε₀', 'S = kB ln Ω',
    'Rμν − ½Rgμν', '∮ F · ds = 0', 'Δx Δp ≥ ℏ/2',
    'eiπ + 1 = 0', '∂μ Fμν = μ₀Jν', 'rₛ = 2GM/c²',
  ];
  for (let row = 0; row < 16; row++) {
    const y = row * 64 + 32;
    context.font = `${row % 3 === 0 ? 'italic ' : ''}${22 + row % 3 * 3}px Georgia, "Times New Roman", serif`;
    context.fillStyle = row % 4 === 0 ? '#ece2ce' : '#aa9a7d';
    for (let col = 0; col < 3; col++) {
      context.fillText(formulas[(row * 5 + col * 3) % formulas.length], col * 342 + 12 + (row * 29 + col * 17) % 55, y, 275);
    }
  }
  return atlas;
}

export async function createGravityRenderer(canvas: HTMLCanvasElement): Promise<GravityRenderer | null> {
  const gl = canvas.getContext('webgl', {
    alpha: false, antialias: false, depth: false, stencil: false,
    powerPreference: 'high-performance', preserveDrawingBuffer: false,
  });
  if (!gl) return null;
  const resources: { shaders: WebGLShader[]; program?: WebGLProgram; buffer?: WebGLBuffer; texture?: WebGLTexture } = { shaders: [] };
  const dispose = () => {
    resources.shaders.forEach(shader => gl.deleteShader(shader));
    if (resources.texture) gl.deleteTexture(resources.texture);
    if (resources.buffer) gl.deleteBuffer(resources.buffer);
    if (resources.program) gl.deleteProgram(resources.program);
  };
  try {
    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type);
      if (!shader) throw new Error('Cannot allocate a scene shader');
      resources.shaders.push(shader);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(`Scene shader: ${gl.getShaderInfoLog(shader)}`);
      return shader;
    };
    const vertex = compile(gl.VERTEX_SHADER, vertexSource);
    const fragment = compile(gl.FRAGMENT_SHADER, fragmentSource);
    const program = gl.createProgram();
    if (!program) throw new Error('Cannot allocate scene program');
    resources.program = program;
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(`Scene program: ${gl.getProgramInfoLog(program)}`);
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    if (!buffer) throw new Error('Cannot allocate scene geometry');
    resources.buffer = buffer;
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const texture = gl.createTexture();
    if (!texture) throw new Error('Cannot allocate formula texture');
    resources.texture = texture;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, createFormulaAtlas());
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
    const anisotropy = gl.getExtension('EXT_texture_filter_anisotropic');
    if (anisotropy) gl.texParameterf(gl.TEXTURE_2D, anisotropy.TEXTURE_MAX_ANISOTROPY_EXT,
      Math.min(8, gl.getParameter(anisotropy.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
    gl.uniform1i(gl.getUniformLocation(program, 'u_formulas'), 0);
    const resolution = gl.getUniformLocation(program, 'u_resolution');
    const time = gl.getUniformLocation(program, 'u_time');
    const rest = gl.getUniformLocation(program, 'u_rest');
    const pointer = gl.getUniformLocation(program, 'u_pointer');
    let targetX = 0, targetY = 0, pointerX = 0, pointerY = 0, previousTime = 0;
    let quality = 1, lastDraw = 0, frameTotal = 0, frameCount = 0;
    const resize = () => {
      const width = Math.max(1, canvas.clientWidth), height = Math.max(1, canvas.clientHeight);
      // Bound ray integration cost on retina/4K screens while preserving glyph detail.
      const pixels = width < 700 ? 750000 : 1500000;
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5, Math.sqrt(pixels / (width * height))) * quality;
      canvas.width = Math.max(1, Math.round(width * ratio));
      canvas.height = Math.max(1, Math.round(height * ratio));
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(resolution, canvas.width, canvas.height);
    };
    resize();
    return {
      resize,
      setPointer(x, y) { targetX = x; targetY = y; },
      render(sceneTime, progress) {
        const now = performance.now();
        const interval = now - lastDraw;
        lastDraw = now;
        // Sample only ordinary playback, never idle time, resize or the deliberate
        // slowdown on entry. Quality settles downward instead of oscillating.
        if (progress < 0.001 && sceneTime > previousTime && interval < 100 && interval > 4) {
          frameTotal += interval;
          if (++frameCount === 45) {
            const average = frameTotal / frameCount;
            if (average > 23 && quality > 0.6) {
              quality = Math.max(0.6, quality * Math.max(0.78, Math.sqrt(19 / average)));
              resize();
            }
            frameTotal = 0;
            frameCount = 0;
          }
        }
        const smoothing = 1.0 - Math.exp(-Math.max(0, sceneTime - previousTime) * 3.0);
        previousTime = sceneTime;
        pointerX += (targetX - pointerX) * smoothing;
        pointerY += (targetY - pointerY) * smoothing;
        gl.uniform2f(pointer, pointerX, pointerY);
        gl.uniform1f(time, sceneTime);
        gl.uniform1f(rest, progress);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
      },
      dispose,
    };
  } catch (error) {
    dispose();
    throw error;
  }
}
