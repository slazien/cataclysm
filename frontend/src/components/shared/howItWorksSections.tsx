import type { ComponentType, ReactNode } from 'react';
import { Activity, Award, Cpu, MessageSquare, Target, TrendingDown, Wrench } from 'lucide-react';

export interface HowItWorksSection {
  icon: ComponentType<{ className?: string }>;
  title: string;
  body: ReactNode;
  slug: string;
}

export const HOW_IT_WORKS_SECTIONS: HowItWorksSection[] = [
  {
    icon: Activity,
    slug: 'data-decoded',
    title: 'Your data, decoded',
    body: (
      <>
        Every CSV you upload contains GPS coordinates sampled hundreds of times per lap, combined
        with your car&apos;s speed and the forces your tires generate. Nolift processes all of
        this in the <strong>distance domain</strong> — meaning every calculation is relative to your
        position on track, not the clock. This is how professional motorsport engineers analyze
        data, and it&apos;s why the analysis is specific to <em>your</em> lines on <em>this</em>{' '}
        track.
      </>
    ),
  },
  {
    icon: Target,
    slug: 'optimal-target',
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
    slug: 'grip-utilization',
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
    slug: 'where-time-went',
    title: 'Where your time went',
    body: (
      <>
        For each corner, Nolift compares the speed you carried through to what your car and
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
    slug: 'corner-grades',
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
    slug: 'ai-coach',
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
    slug: 'equipment',
    title: 'Equipment matters',
    body: (
      <>
        Your Optimal Target changes with your car and tires. Set up an equipment profile and the
        physics model adjusts accordingly — a car with stickier tires or more power has a different
        performance envelope than a stock street car on all-seasons.
        <br />
        <br />
        This means the same lap time means different things depending on your setup. Nolift
        compares your driving against what <em>your</em> equipment can achieve — not a generic
        baseline — so the feedback is always relevant to the car you actually drove.
      </>
    ),
  },
];
