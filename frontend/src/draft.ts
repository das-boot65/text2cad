import type { Spec } from './api';

export function parseDraft(text: string): Spec {
  const value = JSON.parse(text);
  if (!value || !['plate', 'bracket', 'enclosure', 'finger'].includes(value.part_family))
    throw Error('Choose a supported part_family.');
  if (!value.parameters || typeof value.parameters !== 'object' || Array.isArray(value.parameters))
    throw Error('parameters must be an object.');
  if (
    Object.values(value.parameters).some(
      (v) =>
        !(typeof v === 'number' && Number.isFinite(v)) &&
        !(typeof v === 'string' && ['flat', 'tapered'].includes(v)),
    )
  )
    throw Error('Parameters must contain finite numbers or a supported tip value.');
  if (
    value.assumptions !== undefined &&
    (!Array.isArray(value.assumptions) ||
      value.assumptions.some((v: unknown) => typeof v !== 'string'))
  )
    throw Error('assumptions must be an array of strings.');
  if (value.hole_features !== undefined && !Array.isArray(value.hole_features))
    throw Error('hole_features must be an array.');
  return {
    ...value,
    assumptions: value.assumptions ?? [],
    hole_features: value.hole_features ?? [],
    source_text: value.source_text ?? '',
  } as Spec;
}
