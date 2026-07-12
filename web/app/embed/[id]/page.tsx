import SharedAnalysisView from "@/components/SharedAnalysisView";

// Stripped-down, chrome-less analysis view for <iframe> embedding
// (white-label feature). SiteHeader hides itself on /embed/* routes.
export default function EmbedPage({ params }: { params: { id: string } }) {
  return <SharedAnalysisView id={params.id} embed />;
}
