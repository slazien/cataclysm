'use client';

import { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

const DISCLAIMER_KEY = 'cataclysm-disclaimer-accepted';

export function DisclaimerModal() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(DISCLAIMER_KEY)) {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  const handleAccept = () => {
    localStorage.setItem(DISCLAIMER_KEY, new Date().toISOString());
    setVisible(false);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-[var(--cata-border)] px-6 py-4">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400" />
          <h2 className="font-[family-name:var(--font-display)] text-base font-bold text-[var(--text-primary)]">
            Disclaimer &amp; Assumption of Risk
          </h2>
        </div>

        {/* Body */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-4 text-sm leading-relaxed text-[var(--text-secondary)]">
          <p className="mb-3 font-semibold text-[var(--text-primary)]">
            PLEASE READ CAREFULLY BEFORE USING THIS APPLICATION.
          </p>

          <section className="mb-3">
            <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-amber-400">
              Inherent Risks of Motorsport
            </h3>
            <p>
              Track driving and motorsport are inherently dangerous activities that carry significant risk
              of serious injury or death. This application does not eliminate, reduce, or mitigate any risks
              associated with operating a vehicle on a racetrack. You assume all risk.
            </p>
          </section>

          <section className="mb-3">
            <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-amber-400">
              Not Professional Instruction
            </h3>
            <p>
              AI-generated coaching insights are for educational and informational purposes only.
              They are <strong>not a substitute</strong> for professional driving instruction,
              coaching certification, or in-person assessment. Always prioritize guidance from
              certified instructors, track officials, and corner marshals.
            </p>
          </section>

          <section className="mb-3">
            <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-amber-400">
              Data Accuracy
            </h3>
            <p>
              GPS and telemetry accuracy varies by device, environment, and signal conditions.
              AI analysis may contain errors or inaccuracies. Do not rely solely on this data
              for safety-critical decisions. Verify important findings independently.
            </p>
          </section>

          <section className="mb-3">
            <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-amber-400">
              Not Medical Advice
            </h3>
            <p>
              This application does not provide medical or health advice. Consult your physician
              before engaging in track driving activities.
            </p>
          </section>

          <section>
            <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-amber-400">
              No Warranty
            </h3>
            <p>
              This service is provided &quot;as is&quot; without warranties of any kind. We are not liable
              for any direct, indirect, incidental, or consequential damages arising from use of
              this application. Use only for legal track day activities.
            </p>
          </section>
        </div>

        {/* Footer */}
        <div className="border-t border-[var(--cata-border)] px-6 py-4">
          <Button
            size="lg"
            onClick={handleAccept}
            className="w-full bg-[var(--cata-accent)] text-white hover:bg-[var(--cata-accent)]/90"
          >
            I Understand and Accept
          </Button>
        </div>
      </div>
    </div>
  );
}
