'use client';

import { useEffect } from 'react';
import { X, Cpu, Target, Activity, TrendingDown, Award, MessageSquare, Wrench } from 'lucide-react';
import { useUiStore } from '@/stores';
import { cn } from '@/lib/utils';

interface Section {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: React.ReactNode;
}

const SECTIONS: Section[] = [
  {
    icon: Activity,
    title: 'Your data, decoded',
    body: (
      <>
        Every CSV you upload contains GPS coordinates sampled hundreds of times per lap, combined
        with your car&apos;s speed and the forces your tires generate. Cataclysm processes all of
        this in the <strong>distance domain</strong> — meaning every calculation is relative to your
        position on track, not the clock. This is how professional motorsport engineers analyze
        data, and it&apos;s why the analysis is specific to <em>your</em> lines on <em>this</em>{' '}
        track.
      </>
    ),
  },
  {
    icon: Target,
    title: 'The Optimal Target',
    body: (
      <>
        The Optimal Target isn&apos;t a best-sectors average, an industry benchmark, or a guess.
        It&apos;s a <strong>physics simulation</strong>: given your car&apos;s weight and power,
        your tire compound&apos;s grip characteristics, and the G-forces your car actually generated
        this session, what&apos;s the fastest lap that&apos;s physically achievable?
        <br />
        <br />
        The result is a target calibrated to <em>your equipment on this track</em>. The delta
        between your best lap and the Optimal is the realistic time you can find without changing
        your car — just your driving.
      </>
    ),
  },
  {
    icon: Cpu,
    title: 'Grip utilization',
    body: (
      <>
        Your tires have a fixed total grip budget — braking, cornering, and accelerating all compete
        for the same resource. The GG Diagram maps every moment of your session as a point in this
        space. A <strong>fuller shape</strong> means you&apos;re combining forces more effectively
        and using more of what&apos;s available.
        <br />
        <br />
        Gaps in the upper-left (trail braking through turn-in) are the most common source of lost
        time for intermediate drivers. A bigger friction circle doesn&apos;t mean driving harder —
        it means driving smarter.
      </>
    ),
  },
  {
    icon: TrendingDown,
    title: 'Where your time went',
    body: (
      <>
        For each corner, Cataclysm compares the speed you carried through to what your car and
        tires could physically achieve. The gap — converted to seconds — is your{' '}
        <strong>per-corner opportunity</strong>.
        <br />
        <br />
        The Delta-T chart shows this cumulatively around the lap: where the line drops, you&apos;re
        faster than your reference; where it rises, you&apos;re slower. The steepest moves reveal
        exactly where the biggest differences are hiding.
      </>
    ),
  },
  {
    icon: Award,
    title: 'Corner grades',
    body: (
      <>
        Each corner is scored across four dimensions: <strong>Braking</strong> (consistency and
        technique), <strong>Trail Braking</strong> (blending braking into turn-in),{' '}
        <strong>Minimum Speed</strong> (how close you got to the achievable apex speed), and{' '}
        <strong>Throttle Application</strong> (how early and smoothly you commit on exit).
        <br />
        <br />
        Grades are based on your telemetry patterns compared to what good technique looks like at
        each corner type. An A means you&apos;re at or near the limit in that dimension. An F means
        there&apos;s significant untapped time available.
      </>
    ),
  },
  {
    icon: MessageSquare,
    title: 'Your AI coach',
    body: (
      <>
        After every session, an AI model reads your full telemetry — grades, speed gaps, line
        patterns, and consistency data — and generates a coaching report calibrated to your skill
        level. It identifies your highest-leverage opportunity and gives specific, actionable advice.
        <br />
        <br />
        Not &ldquo;brake later.&rdquo; But: <em>where</em> to brake later, by how much, and why
        your current technique is costing you time at that specific corner. The AI coach adapts its
        language and detail level to novice, intermediate, and advanced drivers.
      </>
    ),
  },
  {
    icon: Wrench,
    title: 'Equipment matters',
    body: (
      <>
        Your Optimal Target changes with your car and tires. Set up an equipment profile and the
        physics model adjusts accordingly — a car with stickier tires or more power has a different
        performance envelope than a stock street car on all-seasons.
        <br />
        <br />
        This means the same lap time means different things depending on your setup. Cataclysm
        compares your driving against what <em>your</em> equipment can achieve — not a generic
        baseline — so the feedback is always relevant to the car you actually drove.
      </>
    ),
  },
];

const HOW_IT_WORKS_SEEN_KEY = 'cataclysm-how-it-works-seen';

export function HowItWorksModal() {
  const open = useUiStore((s) => s.howItWorksOpen);
  const toggle = useUiStore((s) => s.toggleHowItWorks);

  // Auto-open once for first-time visitors, but only after disclaimer is accepted
  useEffect(() => {
    if (localStorage.getItem(HOW_IT_WORKS_SEEN_KEY)) return;

    const DISCLAIMER_KEY = 'cataclysm-disclaimer-accepted';

    // Returning user: disclaimer already accepted, show after short delay
    if (localStorage.getItem(DISCLAIMER_KEY)) {
      const timer = setTimeout(toggle, 400);
      return () => clearTimeout(timer);
    }

    // New user: poll until disclaimer is accepted, then show
    const interval = setInterval(() => {
      if (localStorage.getItem(DISCLAIMER_KEY)) {
        clearInterval(interval);
        setTimeout(toggle, 400);
      }
    }, 300);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleClose = () => {
    localStorage.setItem(HOW_IT_WORKS_SEEN_KEY, '1');
    toggle();
  };

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') handleClose();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[55] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div
        className={cn(
          'flex max-h-[90vh] w-full max-w-xl flex-col rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] shadow-2xl',
        )}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-[var(--cata-border)] px-6 py-4">
          <h2 className="font-[family-name:var(--font-display)] text-base font-bold text-[var(--text-primary)]">
            How Cataclysm Works
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close"
            className="flex h-11 w-11 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <p className="mb-5 text-sm leading-relaxed text-[var(--text-secondary)]">
            Cataclysm turns raw telemetry into coaching you can act on. Here&apos;s what the
            numbers actually mean.
          </p>

          <div className="space-y-6">
            {SECTIONS.map((section) => (
              <section key={section.title}>
                <div className="mb-2 flex items-center gap-2">
                  <section.icon className="h-4 w-4 shrink-0 text-[var(--cata-accent)]" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--cata-accent)]">
                    {section.title}
                  </h3>
                </div>
                <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
                  {section.body}
                </p>
              </section>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-[var(--cata-border)] px-6 py-3">
          <p className="text-center text-[11px] text-[var(--text-secondary)]/60">
            Analysis accuracy depends on GPS quality and session length. Results are estimates, not guarantees.
          </p>
        </div>
      </div>
    </div>
  );
}
