import { HOW_IT_WORKS_SECTIONS } from '@/components/shared/howItWorksSections';
import { Button } from '@/components/ui/button';
import Link from 'next/link';

export const metadata = {
  title: 'How It Works — Cataclysm',
  description:
    'Learn how Cataclysm uses physics simulation, grip analysis, and AI coaching to help you find lap time.',
};

export default function HowItWorksPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12 lg:py-20">
      <header className="mb-12 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)] lg:text-4xl font-[family-name:var(--font-display)]">
          How Cataclysm Works
        </h1>
        <p className="mt-4 text-lg text-[var(--text-secondary)]">
          Physics-based coaching, not guesswork. Here&apos;s what happens when you upload a session.
        </p>
      </header>

      <div className="flex flex-col gap-12">
        {HOW_IT_WORKS_SECTIONS.map((section, i) => (
          <section key={section.slug} id={section.slug} className="scroll-mt-20">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--cata-accent)]/10">
                <section.icon className="h-5 w-5 text-[var(--cata-accent)]" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-[var(--text-primary)] font-[family-name:var(--font-display)]">
                  {i + 1}. {section.title}
                </h2>
                <div className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">
                  {section.body}
                </div>
              </div>
            </div>
          </section>
        ))}
      </div>

      {/* CTA */}
      <div className="mt-16 rounded-xl border border-[var(--cata-accent)]/20 bg-[var(--cata-accent)]/5 p-8 text-center">
        <h3 className="text-lg font-semibold text-[var(--text-primary)]">
          Ready to find your lap time?
        </h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Upload a RaceChrono CSV and get physics-based coaching in under a minute.
        </p>
        <Link href="/">
          <Button className="mt-4">Upload Your First Session</Button>
        </Link>
      </div>
    </main>
  );
}
