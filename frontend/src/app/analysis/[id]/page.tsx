export default async function AnalysisPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Analysis: {id}</h1>
      <p className="mt-2 text-[var(--text-secondary)]">Analysis view coming soon.</p>
    </main>
  );
}
