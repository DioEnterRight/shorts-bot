// ENGINE kits/grocery/storeData: solids of the hand-built grocery (store.tsx) and the workshop corner for the checkers,
// same Box format as townData: [x0, x1, y0, y1, z0, z1, label]. Without them the gates cannot see a camera inside a shelf.
export type Box = [number, number, number, number, number, number, string];
export function storeSolids(): Box[] {
  return [
    [-4.1, -1.2, 0, 3.6, 3.93, 4.07, 'grocery wall'], [1.2, 4.1, 0, 3.6, 3.93, 4.07, 'grocery wall'],
    [-1.2, 1.2, 0, 3.6, 3.95, 4.05, 'grocery door'],   // indoor shots stay indoors (no framing through the doorway)
    [-4.1, -3.93, 0, 3.6, -14, 4, 'grocery wall'], [3.93, 4.1, 0, 3.6, -14, 4, 'grocery wall'],
    [-4, 4, 0, 3.6, -14.1, -13.3, 'grocery back shelves'],
    [-1.6, -0.94, 0, 2.2, -11.85, -2.25, 'grocery shelf island'], [0.94, 1.6, 0, 2.2, -11.85, -2.25, 'grocery shelf island'],
    [-3.24, -1.56, 0, 1.06, 1.18, 2.02, 'grocery counter'],
    [-3.76, -3.34, 0.95, 2.3, 0.55, 2.65, 'grocery side shelf'],
    [-2.55, -1.85, 0, 0.7, -1.75, -1.05, 'grocery can pyramid'], [1.85, 2.55, 0, 0.7, -1.75, -1.05, 'grocery can pyramid'],
    [9.8, 11.2, 0, 0.8, 0.74, 1.06, 'workshop bench'],
  ];
}
