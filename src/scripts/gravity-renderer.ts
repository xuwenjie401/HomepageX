/** A single full-resolution GPU pass. The reference composition never rotates.
 * Local advection moves the luminous material and gently flexes the equation sheets.
 * Time is supplied by the controller, so freezing really stops the render loop.
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
uniform sampler2D u_image;
uniform vec2 u_cover;
uniform float u_time;
uniform float u_rest;
varying vec2 v_uv;
const float ASPECT = 1672.0 / 941.0;

void main() {
  vec2 screen = vec2(v_uv.x, 1.0 - v_uv.y);
  vec2 anchor = vec2(0.535, 0.38);
  // Match the poster's object-fit:cover and focal point, including portrait screens.
  vec2 uv = (screen - anchor) * u_cover + anchor;
  // A restrained camera drift comes gently to rest with the scene.
  float zoom = 1.0 + 0.006 * sin(u_time * 0.11) + u_rest * 0.014;
  uv = anchor + (uv - anchor) / zoom;
  vec2 p = (uv - anchor) * vec2(ASPECT, 1.0);
  float r = length(p);
  float angle = atan(p.y, p.x);
  float diskDistance = abs(p.y + 0.53 * p.x);
  float core = smoothstep(0.119, 0.141, r);
  float ring = smoothstep(0.126, 0.157, r) * (1.0 - smoothstep(0.207, 0.255, r));
  float disk = exp(-diskDistance * diskDistance / 0.0015);

  // Keep the diagonal foreground disk anchored while circulating the back light.
  // The larger angular displacement is what makes the filaments visibly flow
  // around the horizon instead of reading as a static poster with a glow.
  float phase = u_time * 0.32;
  float turn = ring * (1.0 - disk * 0.9) *
    (0.105 * sin(phase + r * 23.0) + 0.032 * sin(phase * 1.6 + angle * 5.0));
  float c = cos(turn), s = sin(turn);
  vec2 bent = mat2(c, -s, s, c) * p;
  vec2 flowUv = anchor + bent / vec2(ASPECT, 1.0);

  // Continuous shearing along the two equation sheets. The deformation follows
  // the sheets' perspective, so symbols travel with the ribbon rather than
  // sliding as a flat layer over the image.
  float sheetA = smoothstep(0.34, 0.82, uv.y) * (1.0 - smoothstep(0.02, 0.32, r));
  float sheetB = smoothstep(0.42, 0.82, uv.x) * smoothstep(0.34, 0.8, uv.y);
  float waveA = sin(uv.y * 30.0 - u_time * 1.35 + uv.x * 4.0);
  float waveB = sin(uv.x * 22.0 + u_time * 0.92 - uv.y * 9.0);
  flowUv += vec2(
    (waveA * sheetA * 0.010) + (waveB * sheetB * 0.007),
    (waveB * sheetA * 0.004) - (waveA * sheetB * 0.003)
  );

  // Formula ribbons drift along their perspective planes, not across the sky.
  float lower = smoothstep(0.46, 0.86, uv.y);
  float diagonal = smoothstep(0.28, 0.60, uv.x - uv.y * 0.2);
  float sheet = max(lower, disk * diagonal * 0.45) * (1.0 - ring) * core;
  flowUv += sheet * vec2(
    0.010 * sin(u_time * 0.48 + uv.y * 9.0),
    0.004 * sin(u_time * 0.58 + uv.x * 10.0)
  );
  vec3 color = texture2D(u_image, clamp(flowUv, 0.001, 0.999)).rgb;
  float luminance = dot(color, vec3(0.2126, 0.7152, 0.0722));
  float material = smoothstep(0.05, 0.32, luminance);

  // Fine travelling illumination, restricted to existing gold filaments.
  float filaments = sin(angle * 31.0 - u_time * 2.4 + r * 390.0);
  float swell = sin(angle * 7.0 - u_time * 0.8 + r * 90.0);
  color *= 1.0 + ring * material * (filaments * 0.11 + swell * 0.10);
  float diskPulse = sin(p.x * 44.0 + u_time * 1.45 + p.y * 17.0);
  color *= 1.0 + disk * material * diskPulse * 0.10;
  // Very subtle starlight scintillation; black space remains black.
  float stars = (1.0 - smoothstep(0.38, 0.6, uv.y)) * (1.0 - ring) * (1.0 - disk);
  color *= 1.0 + stars * material * sin(u_time * 1.15 + uv.x * 123.0 + uv.y * 371.0) * 0.10;
  gl_FragColor = vec4(color, 1.0);
}`;

export interface GravityRenderer {
  render: (time: number, rest: number) => void;
  resize: () => void;
  dispose: () => void;
}

export async function createGravityRenderer(canvas: HTMLCanvasElement): Promise<GravityRenderer | null> {
  const gl = canvas.getContext('webgl', {
    alpha: false, antialias: false, depth: false, stencil: false,
    powerPreference: 'low-power', preserveDrawingBuffer: false,
  });
  if (!gl) return null;
  const compile = (type: number, source: string) => {
    const shader = gl.createShader(type);
    if (!shader) throw new Error('Cannot allocate a scene shader');
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const message = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(`Scene shader: ${message}`);
    }
    return shader;
  };
  const vertex = compile(gl.VERTEX_SHADER, vertexSource);
  const fragment = compile(gl.FRAGMENT_SHADER, fragmentSource);
  const program = gl.createProgram()!;
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Cannot link scene shaders');
  gl.useProgram(program);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, 'a_position');
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  const picture = new Image();
  picture.src = canvas.dataset.source!;
  await picture.decode();
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, picture);
  gl.uniform1i(gl.getUniformLocation(program, 'u_image'), 0);
  const cover = gl.getUniformLocation(program, 'u_cover');
  const time = gl.getUniformLocation(program, 'u_time');
  const rest = gl.getUniformLocation(program, 'u_rest');
  const resize = () => {
    const width = canvas.clientWidth, height = canvas.clientHeight;
    // Native retina rendering, capped at a 4K framebuffer to bound GPU memory.
    const ratio = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(8294400 / (width * height)));
    canvas.width = Math.max(1, Math.round(width * ratio));
    canvas.height = Math.max(1, Math.round(height * ratio));
    gl.viewport(0, 0, canvas.width, canvas.height);
    const viewAspect = width / height, imageAspect = picture.width / picture.height;
    gl.uniform2f(cover, Math.min(1, viewAspect / imageAspect), Math.min(1, imageAspect / viewAspect));
  };
  resize();
  return {
    resize,
    render(sceneTime, progress) {
      gl.uniform1f(time, sceneTime);
      gl.uniform1f(rest, progress);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    },
    dispose() {
      gl.deleteTexture(texture);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    },
  };
}
