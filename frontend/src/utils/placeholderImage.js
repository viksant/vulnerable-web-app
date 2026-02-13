/**
 * Generates a deterministic SVG placeholder as a data URI.
 * Each product gets a unique color + icon based on its ID.
 *
 * @param {number|string} productId - Product identifier for color seeding.
 * @param {string} productName - Product name (first letter shown).
 * @returns {string} Data URI of the generated SVG.
 */
export function generatePlaceholderSvg(productId, productName = "?") {
  const id = Number(productId) || 0;
  const hue = (id * 47) % 360;
  const letter = (productName || "?").charAt(0).toUpperCase();

  // Simple geometric pattern varies by product ID
  const patternRotation = (id * 30) % 360;
  const shapeSize = 40 + (id % 5) * 8;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
      <rect width="400" height="400" fill="hsl(${hue}, 60%, 85%)"/>
      <rect x="0" y="0" width="400" height="400" fill="url(#grid)" opacity="0.15"/>
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="black" stroke-width="0.5"/>
        </pattern>
      </defs>
      <g transform="rotate(${patternRotation}, 200, 200)">
        <rect x="${200 - shapeSize}" y="${200 - shapeSize}" width="${shapeSize * 2}" height="${shapeSize * 2}"
              fill="none" stroke="black" stroke-width="4" transform="rotate(45, 200, 200)"/>
      </g>
      <circle cx="200" cy="200" r="60" fill="white" stroke="black" stroke-width="4"/>
      <text x="200" y="218" text-anchor="middle" font-family="system-ui, sans-serif"
            font-size="48" font-weight="900" fill="black">${letter}</text>
      <text x="200" y="370" text-anchor="middle" font-family="system-ui, sans-serif"
            font-size="14" font-weight="700" fill="black" opacity="0.4">NO IMAGE</text>
    </svg>`.trim();

  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}
