'use client';

import { type ReactNode } from 'react';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

interface HeroCardProps {
  children: ReactNode;
  className?: string;
  pulse?: boolean;
}

export function HeroCard({ children, className, pulse = false }: HeroCardProps) {
  return (
    <motion.div
      className={cn(
        'rounded-lg border-l-[3px] border-l-[var(--cata-accent)] bg-gradient-to-r from-[var(--bg-surface)] to-[color-mix(in_srgb,var(--bg-surface)_92%,white)] p-5 lg:p-6',
        className,
      )}
      {...(pulse
        ? {
            animate: {
              scale: [1, 1.03, 1],
              borderLeftColor: [
                'var(--cata-accent)',
                'var(--color-pb)',
                'var(--cata-accent)',
              ],
            },
            transition: {
              duration: 0.6,
              ease: 'easeInOut',
            },
          }
        : {})}
    >
      {children}
    </motion.div>
  );
}
