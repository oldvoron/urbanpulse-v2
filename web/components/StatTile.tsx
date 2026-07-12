export default function StatTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "transport" | "poi" | "risk" | "nature";
}) {
  const accentClass =
    accent === "transport"
      ? "text-accent-transport"
      : accent === "poi"
        ? "text-accent-poi"
        : accent === "risk"
          ? "text-accent-risk"
          : accent === "nature"
            ? "text-accent-nature"
            : "text-ink";
  return (
    <div className="panel px-3 py-2.5">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${accentClass}`}>{value}</div>
    </div>
  );
}
