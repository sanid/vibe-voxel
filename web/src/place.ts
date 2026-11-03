// Which city this page shows. The Berlin page lives at berlin/index.html, so every relative data/ path it fetches
// resolves to berlin/data/ (public/berlin/data, built in cities/berlin/ by the same pipeline: scripts/aoi.py CITY=berlin).
export type City = 'warsaw' | 'berlin';

export const CITY: City = /\/berlin(\/|\/index\.html)?$/.test(location.pathname) ? 'berlin' : 'warsaw';

export const PLACE = CITY === 'berlin'
  ? {
    lat: 52.52, lon: 13.405,
    credits: `<div>Berlin build of <a href="https://github.com/stared/warsaw-vibe-voxel" target="_blank" rel="noopener">warsaw-vibe-voxel</a> by <a href="https://p.migdal.pl/" target="_blank" rel="noopener">Piotr Migdał</a></div>
  <div>based on Geoportal Berlin (DOM1, DGM1, TrueDOP 2024, Baumbestand) and <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap</a></div>`,
    bridge: /(brücke|Brücke|Steg)\b/,
  }
  : {
    lat: 52.23, lon: 21.01,
    credits: `<div>by <a href="https://p.migdal.pl/" target="_blank" rel="noopener">Piotr Migdał</a> & <a href="https://quesma.com/blog/invisible-cities-one-shot/" target="_blank" rel="noopener">Opus 5.5</a>, <a href="https://github.com/stared/warsaw-vibe-voxel" target="_blank" rel="noopener">source code</a></div>
  <div>based on GUGiK 2025 and <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap</a></div>`,
    bridge: /^(Most|Kładka|Wiadukt)\b/,
  };
