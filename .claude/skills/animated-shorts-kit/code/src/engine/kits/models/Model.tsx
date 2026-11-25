// ENGINE kits/models: KayKit CC0 3D models (public/models, list in library/environments/MODELS.md) placed in any set.
// Re-shaded with the kit's flat toon ramp (keeps each model's palette texture), so they match the hand-built sets.
import React from 'react';
import * as THREE from 'three';
import {useLoader} from '@react-three/fiber';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {staticFile} from 'remotion';
import {LOOK_RAMP} from '../../look/look';
import INDEX from '../../../../public/models/index.json';

type V3 = [number, number, number];
/** a placed model: name = 'pack/model' (e.g. 'dungeon/chest_gold'), p = floor position, ry = yaw, s = scale x the pack default */
export type ModelP = {name: string; p: V3; ry?: number; s?: number; tint?: string};

/** pack scales that match the kit's characters (a standing person is ~1.5 m) */
export const PACK_SCALE: Record<string, number> = {city: 3.3, furniture: 0.45, restaurant: 0.45, dungeon: 0.33};

export const modelUrl = (name: string) => {
  const f = (INDEX as Record<string, string>)[name];
  if (!f) throw new Error(`unknown model ${name} (see library/environments/MODELS.md)`);
  return staticFile('models/' + f);
};

const toon = new Map<string, THREE.MeshToonMaterial>();
function toonOf(m: THREE.Material, tint?: string) {
  const src = m as THREE.MeshStandardMaterial, key = (src.map?.uuid ?? '#' + src.color?.getHexString()) + (tint ?? '');
  if (!toon.has(key)) toon.set(key, new THREE.MeshToonMaterial({map: src.map ?? null, color: tint ?? (src.map ? '#ffffff' : src.color), gradientMap: LOOK_RAMP}));
  return toon.get(key)!;
}

export const Model: React.FC<{m: ModelP}> = ({m}) => {
  const gltf = useLoader(GLTFLoader, modelUrl(m.name));
  const obj = React.useMemo(() => {
    const o = gltf.scene.clone(true);
    o.traverse((c) => { const mesh = c as THREE.Mesh; if (!mesh.isMesh) return;
      mesh.material = Array.isArray(mesh.material) ? mesh.material.map((x) => toonOf(x, m.tint)) : toonOf(mesh.material, m.tint);
      mesh.castShadow = mesh.receiveShadow = true; });
    return o;
  }, [gltf, m.tint]);
  const k = (PACK_SCALE[m.name.split('/')[0]] ?? 1) * (m.s ?? 1);
  return <primitive object={obj} position={m.p} rotation={[0, m.ry ?? 0, 0]} scale={[k, k, k]} />;
};

export const Models: React.FC<{list: ModelP[]}> = ({list}) => <>{list.map((m, i) => <Model key={i + m.name} m={m} />)}</>;
