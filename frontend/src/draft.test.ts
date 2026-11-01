import { expect, it } from 'vitest';
import { parseDraft } from './draft';
it('rejects malformed editor shapes without crashing the studio', () => {
  for (const value of [
    null,
    { part_family: 123, parameters: {} },
    { part_family: 'plate', parameters: { length_mm: {} } },
    { part_family: 'plate', parameters: {}, assumptions: [{}] },
  ])
    expect(() => parseDraft(JSON.stringify(value))).toThrow();
});
it('accepts editable parameters but leaves geometric constraints for the server', () => {
  expect(
    parseDraft(JSON.stringify({ part_family: 'plate', parameters: { length_mm: -3 } })).parameters
      .length_mm,
  ).toBe(-3);
});
