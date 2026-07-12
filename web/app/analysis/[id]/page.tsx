import SharedAnalysisView from "@/components/SharedAnalysisView";

// Public shareable view of one completed analysis — no login required.
export default function SharedAnalysisPage({ params }: { params: { id: string } }) {
  return (
    <main className="mx-auto max-w-[1600px] px-4 py-4">
      <SharedAnalysisView id={params.id} />
    </main>
  );
}
