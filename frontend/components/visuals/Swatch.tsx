export function Swatch({ hex, size = 7 }: { hex: string; size?: number }) {
  return (
    <span
      aria-label={hex}
      title={hex}
      className="rounded-full border border-white/15 shrink-0"
      style={{ backgroundColor: hex, width: size * 4, height: size * 4 }}
    />
  );
}
