import type { Metadata } from 'next';
import { Providers } from '@/components/Providers';
import { NetworkStatus } from '@/components/shared/NetworkStatus';
import './globals.css';

export const metadata: Metadata = {
  title: 'Cataclysm — AI Track Coaching',
  description: 'Post-session telemetry analysis and AI coaching for HPDE drivers',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <Providers>
          <NetworkStatus />
          {children}
        </Providers>
      </body>
    </html>
  );
}
