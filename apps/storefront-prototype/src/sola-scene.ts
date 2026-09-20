import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

export type PieceController = {
  setProgress: (value: number) => void;
  setFinish: (index: number) => void;
  dispose: () => void;
};

// A purpose-built furniture study, not a downloaded or production catalogue model.
export function createSolaScene(
  host: HTMLElement,
  onContextLost: () => void,
): PieceController {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 30);
  camera.position.set(2.45, 1.9, 3.5);
  camera.lookAt(0, 0.78, 0);
  const renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
    powerPreference: "low-power",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.35;
  renderer.domElement.setAttribute("aria-hidden", "true");
  host.appendChild(renderer.domElement);

  const fabricCanvas = document.createElement("canvas");
  fabricCanvas.width = fabricCanvas.height = 128;
  const fabricContext = fabricCanvas.getContext("2d")!;
  fabricContext.fillStyle = "#ddd8cc";
  fabricContext.fillRect(0, 0, 128, 128);
  for (let i = 0; i < 128; i += 2) {
    fabricContext.strokeStyle = i % 4 ? "#c7c2b8" : "#ede9e1";
    fabricContext.lineWidth = 0.6;
    fabricContext.beginPath();
    fabricContext.moveTo(i, 0);
    fabricContext.lineTo(i, 128);
    fabricContext.stroke();
    fabricContext.beginPath();
    fabricContext.moveTo(0, i);
    fabricContext.lineTo(128, i);
    fabricContext.stroke();
  }
  const fabricTexture = new THREE.CanvasTexture(fabricCanvas);
  fabricTexture.wrapS = fabricTexture.wrapT = THREE.RepeatWrapping;
  fabricTexture.repeat.set(5, 5);
  fabricTexture.colorSpace = THREE.SRGBColorSpace;
  const fabric = new THREE.MeshStandardMaterial({
    color: "#d8c9ae",
    map: fabricTexture,
    bumpMap: fabricTexture,
    bumpScale: 0.012,
    roughness: 0.94,
  });

  const woodCanvas = document.createElement("canvas");
  woodCanvas.width = woodCanvas.height = 256;
  const woodContext = woodCanvas.getContext("2d")!;
  woodContext.fillStyle = "#c6b69d";
  woodContext.fillRect(0, 0, 256, 256);
  for (let x = 0; x < 256; x += 2) {
    woodContext.strokeStyle = `rgba(75,45,20,${0.04 + (Math.sin(x * 9.17) + 1) * 0.065})`;
    woodContext.lineWidth = 1;
    woodContext.beginPath();
    for (let y = 0; y <= 256; y += 8) {
      const at = x + Math.sin(y / 55 + x / 35) * 3 + Math.sin(y / 110) * 4;
      if (!y) woodContext.moveTo(at, y);
      else woodContext.lineTo(at, y);
    }
    woodContext.stroke();
  }
  const woodTexture = new THREE.CanvasTexture(woodCanvas);
  woodTexture.wrapS = woodTexture.wrapT = THREE.RepeatWrapping;
  woodTexture.colorSpace = THREE.SRGBColorSpace;
  const wood = new THREE.MeshStandardMaterial({
    color: "#997453",
    map: woodTexture,
    roughness: 0.47,
  });
  const seam = new THREE.MeshStandardMaterial({
    color: "#b8a98e",
    roughness: 1,
  });
  const brass = new THREE.MeshStandardMaterial({
    color: "#9c8051",
    roughness: 0.32,
    metalness: 0.65,
  });
  const chair = new THREE.Group();
  scene.add(chair);

  const mesh = (
    geometry: THREE.BufferGeometry,
    material: THREE.Material,
    parent: THREE.Object3D = chair,
  ) => {
    const object = new THREE.Mesh(geometry, material);
    object.castShadow = object.receiveShadow = true;
    parent.add(object);
    return object;
  };
  const rod = (from: number[], to: number[], radius = 0.037) => {
    const start = new THREE.Vector3(...from),
      end = new THREE.Vector3(...to),
      direction = end.clone().sub(start);
    const object = mesh(
      new THREE.CylinderGeometry(radius * 0.92, radius, direction.length(), 20),
      wood,
    );
    object.position.copy(start.add(end).multiplyScalar(0.5));
    object.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      direction.normalize(),
    );
    return object;
  };
  for (const x of [-0.53, 0.53]) {
    rod([x * 1.12, 0.07, 0.5], [x, 0.96, 0.31], 0.045);
    rod([x * 1.08, 0.07, -0.55], [x, 1.4, -0.46], 0.041);
    rod([x, 0.58, 0.38], [x, 0.59, -0.43], 0.039);
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(x, 0.96, 0.43),
      new THREE.Vector3(x * 1.025, 1.02, 0.12),
      new THREE.Vector3(x * 1.02, 1.06, -0.16),
      new THREE.Vector3(x, 1.1, -0.44),
    ]);
    mesh(new THREE.TubeGeometry(curve, 40, 0.048, 16, false), wood);
    for (const endpoint of [curve.getPoint(0), curve.getPoint(1)]) {
      mesh(new THREE.SphereGeometry(0.048, 16, 12), wood).position.copy(
        endpoint,
      );
    }
    for (const z of [-0.38, 0.34]) {
      const joint = mesh(
        new THREE.CylinderGeometry(0.011, 0.011, 0.008, 12),
        brass,
      );
      joint.rotation.z = Math.PI / 2;
      joint.position.set(x + Math.sign(x) * 0.043, 0.59, z);
    }
  }
  rod([-0.53, 0.59, 0.36], [0.53, 0.59, 0.36], 0.045);
  rod([-0.53, 0.59, -0.4], [0.53, 0.59, -0.4], 0.045);
  rod([-0.53, 1.39, -0.46], [0.53, 1.39, -0.46], 0.038);
  rod([-0.52, 0.89, -0.4], [0.52, 0.89, -0.4], 0.034);
  for (let x = -0.37; x <= 0.4; x += 0.185) {
    rod([x, 0.6, -0.4], [x, 0.6, 0.37], 0.018);
    rod([x, 0.83, -0.4], [x, 1.37, -0.46], 0.014);
  }
  const seat = new THREE.Group(),
    back = new THREE.Group();
  chair.add(seat, back);
  seat.position.set(0, 0.715, 0.035);
  seat.rotation.x = -0.035;
  back.position.set(0, 1.08, -0.385);
  back.rotation.x = -0.11;
  mesh(new RoundedBoxGeometry(0.94, 0.2, 0.92, 6, 0.085), fabric, seat);
  mesh(new RoundedBoxGeometry(0.94, 0.68, 0.21, 6, 0.085), fabric, back);
  const piping = (
    width: number,
    depth: number,
    y: number,
    parent: THREE.Object3D,
    vertical = false,
  ) => {
    const points: THREE.Vector3[] = [];
    const radius = 0.065;
    for (let corner = 0; corner < 4; corner++) {
      const x = (corner === 0 || corner === 3 ? 1 : -1) * (width / 2 - radius);
      const z = (corner < 2 ? 1 : -1) * (depth / 2 - radius);
      for (let step = 0; step <= 8; step++) {
        const angle = (corner * Math.PI) / 2 + ((step / 8) * Math.PI) / 2;
        const a = x + Math.cos(angle) * radius,
          b = z + Math.sin(angle) * radius;
        points.push(
          vertical ? new THREE.Vector3(a, b, y) : new THREE.Vector3(a, y, b),
        );
      }
    }
    mesh(
      new THREE.TubeGeometry(
        new THREE.CatmullRomCurve3(points, true),
        100,
        0.003,
        6,
        true,
      ),
      seam,
      parent,
    );
  };
  piping(0.88, 0.86, 0.035, seat);
  piping(0.88, 0.62, 0.058, back, true);

  scene.add(new THREE.HemisphereLight("#fff6e7", "#8d655c", 2.4));
  const key = new THREE.DirectionalLight("#fff3df", 4.3);
  key.position.set(-3, 5, 4);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.camera.left = key.shadow.camera.bottom = -2.5;
  key.shadow.camera.right = key.shadow.camera.top = 2.5;
  key.shadow.normalBias = 0.025;
  key.shadow.bias = -0.0001;
  scene.add(key);
  const fill = new THREE.DirectionalLight("#ffffff", 1.6);
  fill.position.set(4, 2, -3);
  scene.add(fill);
  const floor = mesh(
    new THREE.PlaneGeometry(200, 200),
    new THREE.ShadowMaterial({ opacity: 0.14 }),
    scene,
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0.01;
  floor.castShadow = false;

  let disposed = false,
    frame = 0,
    progress = 0;
  const draw = () => {
    if (frame || disposed) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (!disposed) renderer.render(scene, camera);
    });
  };
  const setProgress = (value: number) => {
    progress = Math.max(0, Math.min(1, value));
    chair.rotation.y = -0.35 + progress * Math.PI * 2;
    const reveal = THREE.MathUtils.smoothstep(progress, 0.63, 0.92);
    seat.position.y = 0.715 + reveal * 0.21;
    back.position.y = 1.08 + reveal * 0.25;
    back.position.z = -0.385 - reveal * 0.28;
    chair.position.y = -reveal * 0.08;
    draw();
  };
  const resize = () => {
    const { width, height } = host.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    // Maintain the full silhouette on narrow canvases.
    camera.fov = camera.aspect < 0.85 ? 43 : 32;
    camera.updateProjectionMatrix();
    draw();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  const lost = (event: Event) => {
    event.preventDefault();
    onContextLost();
  };
  renderer.domElement.addEventListener("webglcontextlost", lost);
  const palettes = [
    { wood: "#997453", fabric: "#e4d3b5", seam: "#baa68a" },
    { wood: "#d0ae7a", fabric: "#79414b", seam: "#5a2b37" },
    { wood: "#4e4843", fabric: "#c8a04f", seam: "#967131" },
  ];
  resize();
  setProgress(progress);
  return {
    setProgress,
    setFinish(index) {
      const palette = palettes[index] || palettes[0];
      wood.color.set(palette.wood);
      fabric.color.set(palette.fabric);
      seam.color.set(palette.seam);
      draw();
    },
    dispose() {
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.domElement.removeEventListener("webglcontextlost", lost);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) object.geometry.dispose();
      });
      [wood, fabric, seam, brass, floor.material].forEach((material) =>
        material.dispose(),
      );
      fabricTexture.dispose();
      woodTexture.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
